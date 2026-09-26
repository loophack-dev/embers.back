# Tasks

## 1. Base de datos

- [x] 1.1 Crear la migración: columna, función y trigger de recálculo, `agents_set_updated_at` que ignora `character_status`, backfill y publicación en `supabase_realtime`; verificar con `npx supabase db reset` y con `pg_publication_tables`

## 2. API y contrato

- [x] 2.1 Leer `character_status` de la columna en `AgentRecord`/`to_agent_out`; actualizar el contrato y el README con la suscripción de Realtime; `ruff` y `mypy` sin errores

## 3. Verificación

- [x] 3.1 Verificar a mano con el runtime falso que la columna pasa por `working`, `waiting` e `idle`, que `updated_at` no cambia y que un cliente de Realtime recibe los `UPDATE`
