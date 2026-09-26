# Spec Delta

## ADDED Requirements

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
