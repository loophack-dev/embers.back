# Proposal

## Why

Embers aún no tiene backend: el repositorio solo contiene los documentos de contrato y de fase. Antes de construir el CRUD de agentes (`add-agent-crud`) se necesita una base ejecutable que arranque, se conecte a Supabase, exponga `GET /health`, responda errores con la forma del contrato y publique eventos en un bus interno que la fase 2 pueda conectar al WebSocket sin tocar los endpoints.

## What Changes

- Estructura del proyecto Python 3.12 gestionado con `uv` (`src/embers/{main.py, config.py, db/, contracts/, domain/, events/, api/routes/}`, `tests/`, `config/`, `supabase/migrations/`), con ruff, mypy (strict) y pytest configurados.
- Configuración por variables de entorno con `pydantic-settings` y un `.env.example` con las variables de la sección 7 del documento de fase, **sin `AWS_REGION`** (ver desviación abajo).
- Proyecto de Supabase (`supabase/config.toml`) para entorno local (`supabase start`) y remoto (`supabase link` + `supabase db push`). En remoto, `DATABASE_URL` apunta al pooler en modo sesión (puerto 5432).
- Pool de `asyncpg` que se abre al arrancar y se cierra al apagar la app (lifespan de FastAPI). La app arranca aunque la base no esté disponible.
- Migración de `workspaces` que inserta la oficina por defecto "Oficina principal" con id fijo (`DEFAULT_WORKSPACE_ID`).
- Bus de eventos interno con sobre igual al del contrato WebSocket (`type`, `event_id`, `ts`, `agent_id`, `task_id`, `data`). En esta fase su único suscriptor escribe cada evento en el log.
- Formato de errores del contrato `{ "error": { "code", "message", "details" } }` para toda la API: validación de FastAPI → `validation_error` (422) con los campos en `details`; rutas inexistentes → `not_found` (404); cualquier excepción no prevista → `internal_error` (500).
- CORS configurable con `CORS_ORIGINS`. Sin autenticación.
- `GET /health` con la forma `HealthOut`: `db`, `storage`, `providers` y `status` (`ok` si `db` es verdadero; si no, `degraded`).
- Logs estructurados en JSON que nunca incluyen API keys.

### Desviación del contrato oficial aprobada

- El enum `Provider` queda con `anthropic`, `openai` y `gemini`. **`bedrock` se elimina** del enum, de `/health.providers`, de `/providers` y de la configuración (no hay `AWS_REGION`). Decisión explícita del usuario ("no uses Bedrock ni AWS").

## Capabilities

### New Capabilities
- `app-config`: configuración por entorno, arranque de la app, ciclo de vida del pool de conexiones, CORS y logs JSON.
- `default-workspace`: tabla `workspaces` y oficina por defecto con id fijo.
- `api-errors`: forma de error del contrato para toda la API, incluidos los errores de validación.
- `health`: `GET /health` según `HealthOut`.
- `event-bus`: bus de eventos interno con el sobre del contrato y suscriptor de log.

### Modified Capabilities
- Ninguna (proyecto nuevo).

## Impact

- Código nuevo en `src/embers/`, `tests/`, `supabase/` y `config/`.
- Dependencias: `fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`, `asyncpg`, `httpx` (chequeo de Storage); de desarrollo: `pytest`, `pytest-asyncio`, `ruff`, `mypy`, `asyncpg-stubs`.
- Requiere Docker y la CLI de Supabase (`npx supabase`) para el entorno local y los tests de integración.
- API pública nueva: `GET /health`. Ningún otro endpoint.
