# Design

## Context

`AgentOut.character_status` hoy se deriva en `to_agent_out` con `AgentRepository.open_tasks`. El front quiere leerlo por Supabase Realtime. Ver proposal.md.

## Decisions

### D1. Trigger en la base, no en la aplicación
Función `public.refresh_agent_character_status(agent_id)` + trigger `after insert or update of status, agent_id or delete on tasks for each row`, que recalcula para `new.agent_id` y `old.agent_id`. Escribe solo si el valor cambia (`is distinct from`), así Realtime no emite actualizaciones vacías.
- Alternativa descartada: escribir desde `TaskService` en cada transición → duplica la regla y se desincroniza ante la recuperación al arrancar, que actualiza tareas por SQL.

### D2. `updated_at` de agentes
El trigger `agents_set_updated_at` pasa a usar `public.agents_set_updated_at()`, que solo actualiza la fecha si cambió algo distinto de `character_status` (compara `to_jsonb(new) - 'character_status' - 'updated_at'` contra `old`).

### D3. Realtime
`alter publication supabase_realtime add table public.agents`, dentro de un bloque que lo omite si ya está publicada (la migración debe poder aplicarse en local y remoto).

### D4. API
`AgentRecord` suma `character_status`; `to_agent_out` lo toma de ahí. `open_tasks` sigue dando `current_task_id` y `queued_task_ids`.

## Risks / Trade-offs

- [RLS desactivado + Realtime] Exposición con la anon key → aceptable en local; activar RLS antes de exponer en remoto.
- [Trigger por fila] Costo mínimo: una consulta indexada por `(agent_id, status)` por cambio de tarea.

## Migration Plan

`npx supabase db reset` / `npx supabase db push`. Rollback: quitar la tabla de la publicación, borrar trigger, función y columna.
