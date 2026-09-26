# tasks Specification

## Purpose
Persiste las tareas delegadas a los agentes y las preguntas que el agente le hace a la persona, con su ciclo de vida.

## Requirements

### Requirement: Tablas de tareas y preguntas
Las migraciones SHALL crear `tasks` y `task_questions` según la sección 3 del documento de fase 2, con la regla de nulos: en `tasks` no aceptan nulo `id`, `workspace_id`, `agent_id`, `instruction` (1–4000), `status`, `agent_snapshot` y `created_at`; en `task_questions`, `id`, `workspace_id`, `task_id`, `question` (1–1000), `status` y `asked_at`. `tasks.status` MUST ser `queued`, `working`, `waiting_user`, `completed`, `failed` o `canceled`; `task_questions.status`, `pending`, `answered` o `expired`; `options`, si existe, una lista de hasta 6 textos. MUST existir como máximo una pregunta `pending` por tarea.

#### Scenario: Segunda pregunta pendiente
- **WHEN** se inserta una segunda pregunta `pending` para la misma tarea
- **THEN** Postgres la rechaza por el índice único parcial

### Requirement: Ciclo de vida de la tarea
Al crearse, la tarea SHALL guardar `agent_snapshot` (nombre, versión, `model_config`, `identity`, `instructions`, `tools` del agente en ese momento). Al empezar MUST pasar a `working` y fijar `started_at` la primera vez. Al preguntar MUST pasar a `waiting_user`; con la respuesta, de nuevo a `working`. Al terminar MUST quedar `completed` o `failed` con `result_text`, `error`, `usage` y `finished_at`.

#### Scenario: Tarea completada
- **WHEN** una tarea termina bien
- **THEN** la fila queda `completed`, con `result_text`, `usage`, `started_at` y `finished_at`, y `error` nulo

#### Scenario: Snapshot inmutable
- **WHEN** el agente se edita después de crear la tarea
- **THEN** `agent_snapshot` de la tarea no cambia

### Requirement: Recuperación al arrancar
Al arrancar el backend, las tareas en `queued`, `working` o `waiting_user` SHALL pasar a `failed` con `error: { code: "internal_error", ... }` y `finished_at`, y sus preguntas `pending` MUST pasar a `expired`.

#### Scenario: Reinicio con tarea abierta
- **WHEN** el backend se reinicia con una tarea en `waiting_user`
- **THEN** la tarea queda `failed` con `internal_error` y su pregunta queda `expired`

### Requirement: Cola por agente
Cada agente SHALL atender una tarea a la vez, en orden de llegada. Una tarea delegada a un agente con una tarea en `working` o `waiting_user`, o con tareas en cola, MUST crearse en `queued`; en otro caso, en `working`. Al terminar la tarea actual (`completed` o `failed`), el agente MUST empezar la siguiente de su cola. Una tarea en `waiting_user` MUST seguir ocupando al agente. Agentes distintos MUST trabajar en paralelo.

#### Scenario: CA3 · Dos delegate seguidos
- **WHEN** se envían dos `delegate` seguidos al mismo agente libre
- **THEN** el primero recibe `ack` con `working`, el segundo con `queued`, y el segundo pasa a `working` solo después del `finish` del primero

#### Scenario: Pregunta ocupa al agente
- **WHEN** la tarea actual está en `waiting_user` y llega otro `delegate` al mismo agente
- **THEN** la nueva tarea queda `queued` hasta que la actual termine

### Requirement: Preguntas a la persona
Cuando el agente usa `ask_user`, la tarea SHALL guardar la pregunta con su `interrupt_id`, pasar a `waiting_user` y enviar `ask`. Con el `answer`, MUST reanudarse la misma instancia del agente con la respuesta asociada al `interrupt_id` y la tarea MUST volver a `working`. Desde la pregunta número `MAX_QUESTIONS_PER_TASK + 1` (por defecto la cuarta), `ask_user` MUST NOT interrumpir y MUST responder al modelo que continúe con supuestos razonables y los mencione en su resumen.

#### Scenario: CA4 · Instrucción ambigua
- **WHEN** se delega "hazme un informe"
- **THEN** llega un `ask`; tras el `answer`, la tarea vuelve a `working` y el `finish` `completed` refleja la respuesta en `result_text`

#### Scenario: Límite de preguntas
- **WHEN** el agente intenta una cuarta pregunta en la misma tarea
- **THEN** no se envía `ask` y el agente continúa hasta el `finish`

### Requirement: Vencimiento de preguntas
Una pregunta sin respuesta durante `ASK_TIMEOUT_S` (por defecto 1.800 s) SHALL marcarse `expired` y la tarea MUST terminar con `finish` fallido y `error.code: "timeout"`.

#### Scenario: Pregunta vencida
- **WHEN** pasa `ASK_TIMEOUT_S` sin `answer`
- **THEN** la pregunta queda `expired`, llega `finish` `failed` con `timeout` y el agente empieza la siguiente tarea de su cola

### Requirement: Tiempos y errores de ejecución
El trabajo del agente (sin contar la espera de respuestas) SHALL limitarse a `TASK_TIMEOUT_S` (por defecto 600 s). Cada situación MUST terminar en `finish` `failed` con: `timeout` si se supera el tiempo; `model_error` si el proveedor devuelve un error, con un mensaje sin datos sensibles; `internal_error` ante un error no previsto. En todos los casos la tarea MUST guardar `error`, `finished_at` y el consumo medido, y el agente MUST pasar a la siguiente tarea de su cola.

#### Scenario: CA11 · Tiempo máximo superado
- **WHEN** el trabajo del agente supera `TASK_TIMEOUT_S`
- **THEN** llega `finish` `failed` con `error.code: "timeout"` y la tarea queda `failed` con `finished_at`

#### Scenario: Error del proveedor
- **WHEN** el proveedor responde con un error (p. ej. API key inválida)
- **THEN** llega `finish` `failed` con `error.code: "model_error"` y el mensaje no contiene la key ni el cuerpo de la respuesta

### Requirement: Resultado de la tarea
Al terminar, `result_text` SHALL ser el último mensaje del agente y `usage` MUST sumar los tokens de entrada, salida y total de toda la tarea, incluidas las reanudaciones, con el `model_id`. `started_at` MUST ser la primera vez que la tarea pasó a `working` y `finished_at` el momento del estado final.

#### Scenario: Consumo con reanudación
- **WHEN** una tarea pregunta, se reanuda y termina
- **THEN** `usage` del `finish` suma el consumo de antes y después de la pregunta

### Requirement: Artefactos en el finish
El `finish` de una tarea SHALL incluir en `artifacts` todos los archivos `ready` de la tarea, en orden de creación y en la forma `ArtifactOut`, cada uno con `download_url` firmada nueva y su `url_expires_at`.

#### Scenario: Varios archivos
- **WHEN** el agente genera un documento y un markdown en la misma tarea
- **THEN** el `finish` trae ambos en `artifacts`, cada uno con `download_url` y `url_expires_at`

### Requirement: Archivo esperado no entregado
Si la tarea trae `expected_output` y al terminar el agente no hay ningún artefacto `ready` de ese tipo, la tarea SHALL terminar `failed` con `error.code: "artifact_error"`, conservando el `result_text` del agente y los artefactos `ready` que sí existan.

#### Scenario: Pidió pptx y no lo generó
- **WHEN** la tarea pide `expected_output: "pptx"` y el agente termina sin crear una presentación
- **THEN** llega `finish` `failed` con `error.code: "artifact_error"` y el `result_text` del agente
