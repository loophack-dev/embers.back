# Tasks

## 1. Scaffolding del proyecto

- [x] 1.1 Crear `pyproject.toml` con `uv` (Python 3.12, paquete `embers` en `src/`), dependencias (`fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `asyncpg`, `httpx`) y de desarrollo (`pytest`, `pytest-asyncio`, `ruff`, `mypy`, `asyncpg-stubs`); verificar que `uv sync` termina sin errores
- [x] 1.2 Configurar ruff, mypy (strict, con plugin de pydantic) y pytest (`asyncio_mode=auto`, marcador `integration`) en `pyproject.toml`; crear la estructura `src/embers/{contracts,domain,db,events,api/routes}/`, `tests/{unit,integration}/`, `config/`; verificar que `uv run ruff check .` y `uv run mypy src` pasan sobre el esqueleto
- [x] 1.3 Crear `.gitignore` (`.env`, `.venv`, cachés, `supabase/.temp`) y verificar que `git status` no muestra archivos generados

## 2. Configuración y logs

- [x] 2.1 Escribir tests unitarios de `Settings`: falta de variable obligatoria, `DEFAULT_WORKSPACE_ID` inválido, opcionales ausentes, `CORS_ORIGINS` separado por comas, secretos ocultos en `repr`
- [x] 2.2 Implementar `src/embers/config.py` con `pydantic-settings` y `SecretStr`; verificar que los tests de 2.1 pasan
- [x] 2.3 Implementar `src/embers/logging.py` (`JsonFormatter` con `ts`, `level`, `logger`, `message`, extras; logs de uvicorn también en JSON); verificado en el log del servidor
- [x] 2.4 Crear `.env.example` con `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL` (local y comentario del pooler en modo sesión para remoto), `DEFAULT_WORKSPACE_ID=00000000-0000-0000-0000-000000000001`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `CORS_ORIGINS`; verificar que `Settings` carga copiándolo a `.env`

## 3. Supabase y oficina por defecto

- [x] 3.1 Ejecutar `npx supabase init` y verificar que existe `supabase/config.toml`
- [x] 3.2 Crear la migración de `workspaces` con la inserción idempotente de la oficina por defecto; verificar con `npx supabase start` + `npx supabase db reset` que aplica limpia
- [x] 3.3 Escribir tests de integración: la tabla tiene las columnas esperadas, existe una sola oficina con el id fijo y nombre "Oficina principal", reejecutar el insert no duplica, y la oficina de `DEFAULT_WORKSPACE_ID` existe; verificar que pasan contra el Supabase local

## 4. Pool de base de datos

- [x] 4.1 Escribir tests: `ping()` es `true` contra el Supabase local, `false` con un `DATABASE_URL` a un puerto cerrado (en < 3 s), y `open()` no falla con la base caída
- [x] 4.2 Implementar `src/embers/db/pool.py` (`Database` con `open/close/acquire/ping`, `min_size=0`); verificar que los tests de 4.1 pasan

## 5. Formato de errores

- [x] 5.1 Escribir tests: validación de cuerpo anidado (`identity.role`), JSON mal formado (`field: "body"`), ruta inexistente (404 `not_found`), método no permitido (405 `not_found`), excepción no prevista (500 `internal_error`, `details: null`, traza en el log y no en la respuesta), y `details` siempre presente; usar rutas de prueba montadas solo en el test
- [x] 5.2 Implementar `contracts/errors.py` (`ErrorCode`, `ErrorBody`, `ErrorResponse`), `errors.py` (`ApiError`) y `api/errors.py` (handlers); verificar que los tests de 5.1 pasan

## 6. Bus de eventos

- [x] 6.1 Escribir tests: sobre del evento (`event_id: null`, `ts` en UTC), entrega en orden a varios suscriptores, aislamiento de un suscriptor que falla (con log del fallo), `LogSubscriber` registra `type` y `data` en JSON y redacta `data.agent.instructions` largo
- [x] 6.2 Implementar `events/bus.py` (`Event`, `Subscriber`, `EventBus`) y `events/log_subscriber.py`; verificar que los tests de 6.1 pasan

## 7. App y `/health`

- [x] 7.1 ~~Tests de `/health`~~ Descartado: el usuario pidió no escribir más tests. Verificado a mano: `ok` con base disponible, `degraded` con base caída, forma exacta de `HealthOut`
- [x] 7.2 Implementar `contracts/health.py`, `api/deps.py`, `api/routes/health.py` y `main.py` (`create_app` con lifespan que abre/cierra `Database`, `httpx.AsyncClient` y `EventBus` con `LogSubscriber`); verificar con `curl /health`
- [x] 7.3 Configurar `CORSMiddleware` desde `CORS_ORIGINS`; verificado con `curl`: el origen permitido recibe la cabecera y el no permitido no
- [x] 7.4 Verificar arranque manual: `uv run embers` (`uvicorn embers.main:create_app --factory`) con el Supabase local, `curl /health` devuelve `ok` y los logs salen en JSON

## 8. Documentación e integración final

- [x] 8.1 Escribir `README.md` con requisitos, arranque local (`npx supabase start`, `db reset`, `.env`, `uvicorn`), conexión al Supabase remoto (`supabase link`, `db push`, pooler en modo sesión) y cómo correr tests/lint; verificar que los comandos documentados funcionan tal cual
- [x] 8.2 Verificar `uv run ruff check .`, `uv run ruff format --check .` y `uv run mypy src` sin errores (sin suite de tests por decisión del usuario)
