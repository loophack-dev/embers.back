# Spec Delta

## MODIFIED Requirements

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
