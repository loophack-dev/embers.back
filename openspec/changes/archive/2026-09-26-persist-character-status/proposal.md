# Proposal

## Why

El front necesita ver el estado del personaje (`idle`, `working`, `waiting`) directamente desde la base, suscrito con Supabase Realtime, para animar la oficina al instante. Hoy `character_status` solo existe en la respuesta REST (`AgentOut`), calculado a partir de las tareas.

## What Changes

- Columna **`agents.character_status`** (`text`, no nulo, por defecto `'idle'`, check `idle | working | waiting`).
- **Trigger sobre `tasks`** (insert, update de `status` o `agent_id`, delete) que recalcula el estado del agente: `working` si tiene una tarea en `working`, `waiting` si tiene una en `waiting_user`, `idle` si no. La base es la única que lo escribe, así que no puede desincronizarse del estado de las tareas.
- El cambio de `character_status` **no** modifica `agents.updated_at` (que sigue reflejando cambios de configuración).
- La tabla **`agents`** se agrega a la publicación **`supabase_realtime`** para que el front reciba los cambios.
- `AgentOut.character_status` pasa a leerse de la columna (misma regla, mismo valor). `current_task_id` y `queued_task_ids` siguen calculándose por REST.
- Contrato actualizado: `CharacterStatus` se guarda en `agents.character_status`, mantenida por trigger y publicada en Realtime.

### Precisiones a aprobar

1. **Solo `character_status`** va a la base; `current_task_id` y `queued_task_ids` no (no se pidieron).
2. **Seguridad**: RLS sigue desactivado (decisión del contrato para el demo). Con Realtime, cualquiera con la anon key del proyecto recibe los cambios de `agents` (incluidas `instructions`). Es aceptable en local; antes de exponerlo en remoto habría que activar RLS con una política de solo lectura.
3. **Backfill**: la migración calcula el estado de los agentes existentes.

## Capabilities

### New Capabilities
- Ninguna.

### Modified Capabilities
- `agents`: el estado del personaje se persiste en la base y se publica en Realtime.

## Impact

- Una migración nueva; `db/agents_repository.py` y `domain/agents.py` leen la columna; `docs/embers-modelos-y-contratos.md`.
- El front se suscribe con `supabase.channel('agents').on('postgres_changes', { event: 'UPDATE', schema: 'public', table: 'agents' }, ...)`.
- Sin tests automatizados (decisión del usuario).
