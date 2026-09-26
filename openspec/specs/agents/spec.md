# agents Specification

## Purpose
Permite crear, consultar, editar, dar apariencia y archivar agentes de IA de la oficina por defecto, persistidos en Supabase y expuestos con los contratos REST oficiales (`AgentCreate`, `AgentUpdate`, `AgentOut`, `AppearanceUpdate`).

## Requirements

### Requirement: Persistencia del agente con regla de nulos
Las migraciones SHALL crear `agents` y `ui_settings` según la sección 3 del documento de fase. En `agents`, `name`, `model_config`, `identity`, `workspace_id`, `status`, `version`, `created_at` y `updated_at` MUST ser no nulos; `instructions` y `tools` MUST aceptar nulo. `model_config` MUST ser un objeto con las llaves `provider` y `model_id`; `identity` MUST ser un objeto con la llave `role`; `status` MUST ser `active` o `archived`. El nombre MUST ser único entre los agentes activos de la misma oficina. `updated_at` MUST actualizarse en cada modificación. En `ui_settings`, `data` MUST aceptar nulo y la combinación (`workspace_id`, `owner_type`, `owner_id`, `namespace`) MUST ser única.

#### Scenario: CA1 · Migraciones sobre base vacía
- **WHEN** se aplican todas las migraciones sobre un Supabase vacío, local o remoto
- **THEN** terminan sin errores, existen `workspaces`, `agents` y `ui_settings`, y la oficina por defecto existe

#### Scenario: La base rechaza un agente sin rol
- **WHEN** se inserta directamente en `agents` una fila cuyo `identity` no tiene `role`
- **THEN** Postgres rechaza la inserción por el check

#### Scenario: Nombre libre tras archivar
- **WHEN** existe un agente archivado llamado "Ana" y se inserta un agente activo "Ana" en la misma oficina
- **THEN** la inserción es aceptada

### Requirement: Forma de AgentOut
Toda respuesta que devuelve un agente SHALL tener exactamente los campos de `AgentOut`: `id`, `name`, `model_config`, `identity`, `instructions`, `tools`, `status`, `version`, `appearance`, `character_status`, `current_task_id`, `queued_task_ids`, `created_at`, `updated_at`. Los valores nulos de la base MUST convertirse así: `instructions` → `""`, `tools` → `[]`, apariencia ausente o con `data` nulo → `{}`, `model_config.params` ausente o vacío → `null` (si hay algún parámetro, `params` es el objeto completo con cada parámetro ausente en `null`), `identity.persona` e `identity.tone` ausentes → `null`. `character_status` MUST ser `working` si el agente tiene una tarea en `working`, `waiting` si tiene una en `waiting_user` e `idle` si no; `current_task_id` MUST ser esa tarea o `null`; `queued_task_ids` MUST listar sus tareas `queued` en orden de creación. Las fechas MUST ir en ISO 8601 en UTC. La respuesta MUST NOT incluir `workspace_id` ni otros campos internos.

#### Scenario: CA10 · Contrato campo por campo
- **WHEN** cualquier endpoint devuelve un agente
- **THEN** el objeto valida contra `AgentOut` y su conjunto de llaves (incluidas las de `model_config`, `model_config.params` e `identity`) es exactamente el del contrato

#### Scenario: CA10 · Estado del personaje durante la tarea
- **WHEN** se consulta `GET /agents/{id}` durante una tarea, con una pregunta pendiente y al terminar
- **THEN** `character_status` es `working`, luego `waiting` y luego `idle`, y `current_task_id` es la tarea mientras no termina

#### Scenario: Tareas en cola
- **WHEN** el agente tiene una tarea en curso y dos en cola
- **THEN** `queued_task_ids` lista las dos en orden de llegada

### Requirement: Crear agente (POST /agents)
`POST /agents` SHALL validar el cuerpo contra `AgentCreate`, guardar el agente en la oficina por defecto con `status: active` y `version: 1`, y responder 201 con `AgentOut`. `model_config.provider` MUST ser `anthropic`, `openai` o `gemini` y `model_id` MUST estar en el catálogo de ese proveedor; si no, `validation_error`. El agente MUST poder crearse aunque el proveedor no tenga API key. Si `tools` no se envía, MUST guardarse con las tres herramientas del demo; si se envía `[]`, MUST guardarse vacía; cada id MUST existir en el catálogo o la respuesta es `unknown_tool`. Un `instructions` vacío o ausente MUST guardarse como nulo. Si viene `appearance` (objeto de hasta 64 KB), MUST guardarse en `ui_settings` con `owner_type: agent` y `namespace: appearance`, en la misma transacción que el agente.

#### Scenario: CA3 · Agente mínimo
- **WHEN** se crea un agente solo con `name`, `model_config` (`provider` y `model_id`) e `identity` (`role`)
- **THEN** la respuesta es 201, la fila tiene `instructions` nulo, y la respuesta muestra `instructions: ""`, `appearance: {}` y `tools: ["create_document", "create_presentation", "create_markdown"]`

#### Scenario: CA4 · Falta model_config
- **WHEN** se crea un agente sin `model_config`
- **THEN** la respuesta es 422 con `code: "validation_error"` y `details.fields` incluye `model_config`

#### Scenario: CA4 · Falta identity.role
- **WHEN** se crea un agente con `identity: {}`
- **THEN** la respuesta es 422 con `code: "validation_error"` y `details.fields` incluye `identity.role`

#### Scenario: CA5 · Modelo fuera del catálogo
- **WHEN** se crea un agente con `model_config: { "provider": "openai", "model_id": "gpt-0" }`
- **THEN** la respuesta es 422 con `code: "validation_error"` y `details.fields` incluye `model_config.model_id`

#### Scenario: Proveedor fuera del enum
- **WHEN** se crea un agente con `provider: "bedrock"`
- **THEN** la respuesta es 422 con `code: "validation_error"` en `model_config.provider`

#### Scenario: CA6 · Herramienta desconocida
- **WHEN** se crea un agente con `tools: ["create_document", "send_email"]`
- **THEN** la respuesta es 422 con `code: "unknown_tool"` y nada se guarda

#### Scenario: Lista de herramientas vacía
- **WHEN** se crea un agente con `tools: []`
- **THEN** la respuesta muestra `tools: []`

#### Scenario: Proveedor sin API key
- **WHEN** se crea un agente de `gemini` y el servidor no tiene `GEMINI_API_KEY`
- **THEN** la respuesta es 201

#### Scenario: Nombre duplicado
- **WHEN** ya existe un agente activo "Ana" y se crea otro "Ana"
- **THEN** la respuesta es 422 con `code: "validation_error"` en `name`

#### Scenario: Creación con apariencia
- **WHEN** se crea un agente con `appearance: { "avatar": "fox", "color": "#ff8800" }`
- **THEN** la respuesta muestra exactamente esa `appearance`

### Requirement: Listar agentes (GET /agents)
`GET /agents` SHALL responder `{ "items": [AgentOut] }` con los agentes de la oficina por defecto ordenados por `created_at` ascendente. Sin parámetros o con `include_archived=false` MUST incluir solo los activos; con `include_archived=true` MUST incluir también los archivados.

#### Scenario: Lista sin archivados
- **WHEN** hay un agente activo y uno archivado y se hace `GET /agents`
- **THEN** `items` contiene solo el activo

#### Scenario: Lista con archivados
- **WHEN** se hace `GET /agents?include_archived=true`
- **THEN** `items` contiene ambos, en orden de creación

### Requirement: Consultar un agente (GET /agents/{id})
`GET /agents/{id}` SHALL responder `AgentOut`, incluso si el agente está archivado (con `status: archived`). Si no existe, MUST responder 404 `not_found`. Si `id` no es un UUID, MUST responder 422 `validation_error`.

#### Scenario: Agente archivado
- **WHEN** se consulta un agente archivado
- **THEN** la respuesta es 200 con `status: "archived"`

#### Scenario: Agente inexistente
- **WHEN** se consulta un UUID que no existe
- **THEN** la respuesta es 404 con `code: "not_found"`

### Requirement: Editar agente (PATCH /agents/{id})
`PATCH /agents/{id}` SHALL cambiar solo los campos enviados y responder `AgentOut`. `model_config` e `identity` MUST reemplazarse completos, sin mezclarse con los anteriores. `name`, `model_config` o `identity` en `null` MUST responder `validation_error`. `instructions: null` o `""` MUST guardar nulo; `tools: null` MUST guardar nulo. Las mismas validaciones de catálogo y nombre de la creación MUST aplicarse. `version` MUST subir en 1 si cambia `model_config`, `identity`, `instructions` o `tools`, y MUST NOT subir si solo cambia `name`. Un agente archivado MUST responder 409 `agent_archived`. Si hubo cambios, MUST publicar `agent.updated`.

#### Scenario: CA7 · Editar instrucciones sube la versión
- **WHEN** un agente en `version: 1` recibe `PATCH { "instructions": "Be concise." }`
- **THEN** la respuesta muestra `version: 2` e `instructions: "Be concise."`

#### Scenario: CA7 · Editar solo el nombre no sube la versión
- **WHEN** un agente en `version: 1` recibe `PATCH { "name": "Nuevo nombre" }`
- **THEN** la respuesta muestra `version: 1` y el nuevo nombre

#### Scenario: Reemplazo completo de identity
- **WHEN** un agente con `identity: { "role": "A", "persona": "P", "tone": "T" }` recibe `PATCH { "identity": { "role": "B" } }`
- **THEN** la respuesta muestra `identity: { "role": "B", "persona": null, "tone": null }`

#### Scenario: Null explícito en campo obligatorio
- **WHEN** se envía `PATCH { "model_config": null }`
- **THEN** la respuesta es 422 con `code: "validation_error"` en `model_config`

#### Scenario: Sin cambios reales
- **WHEN** se envía un PATCH con los mismos valores guardados
- **THEN** la respuesta es 200, `version` no cambia y no se publica evento

#### Scenario: CA9 · Editar un agente archivado
- **WHEN** se envía un PATCH a un agente archivado
- **THEN** la respuesta es 409 con `code: "agent_archived"`

### Requirement: Guardar apariencia (PUT /agents/{id}/appearance)
`PUT /agents/{id}/appearance` SHALL recibir `AppearanceUpdate` (`{ "data": objeto }`), reemplazar completa la apariencia del agente y responder `AgentOut`. El backend MUST NOT interpretar el contenido de `data`. Si `data` supera 64 KB, MUST responder 422 `validation_error`. MUST NOT subir `version`. Un agente archivado MUST responder 409 `agent_archived`; uno inexistente, 404 `not_found`. MUST publicar `agent.updated`.

#### Scenario: CA8 · Ida y vuelta exacta
- **WHEN** se guarda `data: { "avatar": "fox", "color": "#ff8800", "desk": { "x": 3, "y": 5 } }` y luego se hace `GET /agents/{id}`
- **THEN** `appearance` es exactamente ese objeto y `version` no cambió

#### Scenario: Reemplazo completo
- **WHEN** después se guarda `data: { "avatar": "owl" }`
- **THEN** `appearance` es exactamente `{ "avatar": "owl" }`

#### Scenario: Apariencia demasiado grande
- **WHEN** `data` serializado pesa más de 64 KB
- **THEN** la respuesta es 422 con `code: "validation_error"` en `data`

### Requirement: Archivar agente (DELETE /agents/{id})
`DELETE /agents/{id}` SHALL cambiar `status` a `archived` sin borrar la fila y responder 204 sin cuerpo. Si ya estaba archivado, MUST responder 204 sin publicar de nuevo. Si no existe, MUST responder 404 `not_found`. Tras archivarlo, su nombre MUST quedar libre para un agente nuevo. MUST publicar `agent.archived`.

#### Scenario: CA9 · Archivar saca de la lista y libera el nombre
- **WHEN** se archiva el agente "Ana"
- **THEN** la respuesta es 204, `GET /agents` ya no lo incluye y un `POST /agents` con nombre "Ana" responde 201

#### Scenario: Archivado idempotente
- **WHEN** se archiva dos veces el mismo agente
- **THEN** ambas respuestas son 204

### Requirement: Eventos del agente en el bus interno
Cada escritura SHALL publicar su evento en el bus interno, visible en el log: `POST /agents` → `agent.created` con `data: { "agent": AgentOut }`; `PATCH` con cambios y `PUT .../appearance` → `agent.updated` con `data: { "agent": AgentOut }`; `DELETE` que archiva → `agent.archived` con `data: { "agent_id" }`. El `agent_id` del sobre MUST ser el id del agente y `task_id` MUST ser `null`. El evento MUST publicarse después de confirmar la transacción.

#### Scenario: CA11 · Eventos en el log
- **WHEN** se crea, edita, cambia la apariencia y archiva un agente
- **THEN** el log contiene, en ese orden, `agent.created`, `agent.updated`, `agent.updated` y `agent.archived`, cada uno con el `data` del contrato y sin el texto completo de `instructions`

### Requirement: Estado del personaje en la base
La tabla `agents` SHALL tener la columna `character_status` (no nula, `idle`, `working` o `waiting`), mantenida por la base a partir de las tareas del agente: `working` si tiene una tarea en `working`, `waiting` si tiene una en `waiting_user`, `idle` si no. Cambiar `character_status` MUST NOT modificar `updated_at`. La tabla `agents` MUST estar en la publicación `supabase_realtime`. `AgentOut.character_status` MUST coincidir con la columna.

#### Scenario: Cambios durante una tarea
- **WHEN** un agente recibe una tarea, el agente pregunta y la tarea termina
- **THEN** `agents.character_status` pasa por `working`, `waiting` e `idle`, y un cliente suscrito a Realtime recibe cada `UPDATE`

#### Scenario: updated_at no cambia
- **WHEN** cambia solo el estado del personaje
- **THEN** `agents.updated_at` conserva su valor

#### Scenario: Backfill
- **WHEN** se aplica la migración con un agente que ya tiene una tarea en `working`
- **THEN** su `character_status` queda en `working`
