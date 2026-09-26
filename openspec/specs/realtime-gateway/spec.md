# realtime-gateway Specification

## Purpose
Canal WebSocket `/ws` por el que el front delega tareas y responde preguntas, y el backend confirma, pregunta y entrega resultados, con el protocolo de la sección 5 del contrato oficial.

## Requirements

### Requirement: Sobre de los mensajes
El endpoint `/ws` SHALL aceptar mensajes JSON `{ type, request_id, data }` con `type` `delegate` o `answer`, y SHALL enviar mensajes con exactamente los campos `type`, `event_id`, `ts`, `agent_id`, `task_id`, `request_id` y `data`. `event_id` MUST ser el id del mensaje en `task_events` y `ts` su fecha en ISO 8601 UTC. `request_id` MUST ser el del mensaje recibido en `ack` y `error`, y `null` en `ask` y `finish`.

#### Scenario: Forma de un mensaje saliente
- **WHEN** el servidor envía cualquier mensaje
- **THEN** tiene exactamente `type`, `event_id` (entero), `ts`, `agent_id`, `task_id`, `request_id` y `data`, y su `data` cumple el objeto del contrato para ese `type` sin campos de más ni de menos

### Requirement: Delegar una tarea
Un `delegate` válido SHALL crear una tarea con la copia de la configuración del agente y responder `ack` solo a la conexión que lo envió, con `data: { task_id, status }` y `agent_id`/`task_id` en el sobre. `status` MUST ser `working` si el agente está libre y `queued` si está ocupado.

#### Scenario: Delegate válido recibe ack
- **WHEN** una conexión envía `delegate` con un `agent_id` activo y libre y una `instruction` válida
- **THEN** esa conexión recibe `ack` con el `request_id` enviado, `data.task_id` de la tarea creada y `data.status: "working"`, y las demás conexiones no reciben ese `ack`

#### Scenario: Agente ocupado
- **WHEN** el agente ya tiene una tarea en curso
- **THEN** el `ack` trae `data.status: "queued"`

#### Scenario: CA2 · Delegate rechazado no crea tarea
- **WHEN** se envía `delegate` a un agente archivado, inexistente o sin API key de su proveedor (con `AGENT_RUNTIME=strands`)
- **THEN** se recibe `error` con `agent_archived`, `not_found` o `provider_unavailable` y la tabla `tasks` no cambia

### Requirement: Validación de delegate
Un `delegate` inválido SHALL responder `error` solo a quien lo envió, con `data` = ErrorBody, y MUST NOT crear ninguna tarea. Códigos: `validation_error` si faltan `request_id` o `data`, o si `agent_id`, `instruction` (1–4000) o `expected_output` (`docx`, `pptx`, `md` o `null`) no cumplen el contrato; `not_found` si el agente no existe; `agent_archived` si está archivado; `provider_unavailable` si el servidor no tiene API key de su proveedor (no aplica con `AGENT_RUNTIME=fake`). `details` de `validation_error` MUST tener la forma `{ "fields": [ { "field", "reason" } ] }`.

#### Scenario: Agente inexistente
- **WHEN** se envía `delegate` con un `agent_id` que no existe
- **THEN** se recibe `error` con `code: "not_found"` y no se crea ninguna tarea

#### Scenario: Agente archivado
- **WHEN** se envía `delegate` a un agente archivado
- **THEN** se recibe `error` con `code: "agent_archived"` y no se crea ninguna tarea

#### Scenario: Proveedor sin API key
- **WHEN** `AGENT_RUNTIME=strands`, el agente es de `gemini` y no hay `GEMINI_API_KEY`
- **THEN** se recibe `error` con `code: "provider_unavailable"` y no se crea ninguna tarea

#### Scenario: Instrucción vacía
- **WHEN** se envía `delegate` con `instruction: ""`
- **THEN** se recibe `error` con `code: "validation_error"` y `details.fields` incluye `instruction`

### Requirement: Validación de answer
Un `answer` SHALL validarse así, respondiendo `error` solo a quien lo envió y sin cambiar nada: `validation_error` si `task_id`, `question_id` o `answer` (1–2000) no cumplen el contrato; `not_found` si la tarea o la pregunta no existen o la pregunta no es de esa tarea; `question_not_pending` si la pregunta no está `pending` o la tarea no está en `waiting_user`. Un `answer` válido MUST responder `ack` con `data: { task_id, status: "working" }`.

#### Scenario: Answer válido
- **WHEN** se responde la pregunta pendiente de una tarea en `waiting_user`
- **THEN** quien lo envió recibe `ack` con `status: "working"`

#### Scenario: Pregunta ya respondida
- **WHEN** se envía un `answer` a una pregunta ya respondida
- **THEN** se recibe `error` con `code: "question_not_pending"`

#### Scenario: Pregunta de otra tarea
- **WHEN** se envía un `answer` con un `question_id` que pertenece a otra tarea
- **THEN** se recibe `error` con `code: "not_found"`

### Requirement: Mensaje desconocido
Un mensaje que no es JSON válido o cuyo `type` no es `delegate` ni `answer` SHALL responder `error` con `code: "unknown_command"` solo a quien lo envió, sin cerrar la conexión. Si no se pudo leer `request_id`, el `error` MUST llevar `request_id: null`.

#### Scenario: Type desconocido
- **WHEN** se envía `{ "type": "hello", "request_id": "r1", "data": {} }`
- **THEN** se recibe `error` con `code: "unknown_command"` y `request_id: "r1"`, y la conexión sigue abierta

#### Scenario: JSON inválido
- **WHEN** se envía el texto `not json`
- **THEN** se recibe `error` con `code: "unknown_command"` y `request_id: null`

### Requirement: Difusión de ask y finish
`ask` y `finish` SHALL enviarse a todas las conexiones abiertas en ese momento. Si no hay conexiones, MUST quedar guardados en `task_events` sin error.

#### Scenario: Dos conexiones
- **WHEN** hay dos conexiones abiertas y una delega una tarea
- **THEN** ambas conexiones reciben el `finish` de esa tarea (y el `ask`, si lo hay), pero solo la que delegó recibe el `ack`

### Requirement: Reenvío de preguntas pendientes
Al abrir una conexión, el servidor SHALL enviarle los `ask` de las preguntas `pending`, en orden de creación, reenviando el mismo mensaje original (mismo `event_id`).

#### Scenario: Reconexión con ask pendiente
- **WHEN** el front se desconecta con un `ask` pendiente y vuelve a conectarse
- **THEN** la nueva conexión recibe ese `ask` con el mismo `event_id` y `question_id`

### Requirement: Registro en task_events
Cada mensaje que entra o sale por `/ws` SHALL guardarse en `task_events` con su `type`, `direction` (`in` o `out`), `task_id` y `agent_id` cuando apliquen, y el mensaje en `data` (sin `event_id` ni `ts`). Un mensaje entrante ilegible MUST guardarse con `type: "unknown"` y `data: { "raw": <texto truncado> }`.

#### Scenario: Flujo registrado
- **WHEN** se completa `delegate` → `ack` → `ask` → `answer` → `ack` → `finish`
- **THEN** `task_events` tiene esas seis filas en orden, con `direction` `in`, `out`, `out`, `in`, `out`, `out`
