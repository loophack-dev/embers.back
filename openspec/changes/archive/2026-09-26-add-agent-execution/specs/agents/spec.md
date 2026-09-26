# Spec Delta

## MODIFIED Requirements

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
