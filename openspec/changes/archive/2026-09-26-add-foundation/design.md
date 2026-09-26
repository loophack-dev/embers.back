# Design

## Context

Repositorio vacío salvo `docs/` y `openspec/`. Ver proposal.md (Why). Restricciones del stack en `openspec/config.yaml`. Entorno disponible: Docker 29, Supabase CLI 2.118 vía `npx supabase`, Python 3.12 vía `uv`.

La arquitectura debe dejar lugar para la fase 2 (WebSocket), la fase 3 (runtime con Strands, artefactos, Storage) y la fase 4 (memoria) sin implementarlas.

## Goals / Non-Goals

**Goals:**
- Capas con dependencias hacia adentro: `api` → `domain` ← `db`; `contracts` es el borde REST/WS; `events` no conoce el transporte.
- Todo lo que sale por la API se tipa con modelos Pydantic del contrato (`extra="forbid"` en entradas).
- La app arranca y responde `/health` aunque Postgres esté caído.

**Non-Goals:**
- Autenticación, WebSocket, persistencia de eventos (`task_events`), Storage de artefactos.
- Tablas distintas de `workspaces`.

## Decisions

### D1. Estructura y capas

```
src/embers/
├─ main.py            create_app(): FastAPI + lifespan + middlewares + handlers + routers
├─ config.py          Settings (pydantic-settings), get_settings()
├─ logging.py         JsonFormatter + configure_logging()
├─ errors.py          ApiError(code, message, details, status) + ErrorCode
├─ contracts/         Modelos del contrato oficial: errors.py (ErrorBody), health.py (HealthOut), common.py (Provider)
├─ domain/            vacío en esta fase (lo llena add-agent-crud)
├─ db/pool.py         Database: open()/close()/acquire()/ping()
├─ events/            bus.py (Event, EventBus, Subscriber), log_subscriber.py
└─ api/
   ├─ deps.py         Dependencias FastAPI (get_db, get_bus, get_settings) leídas de app.state
   ├─ errors.py       exception handlers
   └─ routes/health.py
```

Dependencias vía `app.state` + `Depends`, no globales de módulo: los tests construyen la app con settings y dobles propios.

### D2. Configuración
`pydantic-settings` con `SecretStr` para `SUPABASE_SERVICE_ROLE_KEY` y API keys (su `repr` nunca muestra el valor). `DEFAULT_WORKSPACE_ID: UUID`, `CORS_ORIGINS` como texto separado por comas convertido a lista. Sin `AWS_REGION` (proposal: desviación aprobada).

### D3. Pool de asyncpg tolerante a la base caída
`asyncpg.create_pool(min_size=0, max_size=10)` en el lifespan: con `min_size=0` no abre conexiones al crearse, así que la app arranca con la base caída y cada `acquire()` reintenta. `ping()` hace `SELECT 1` con `timeout=2`. `close()` en el apagado.
- Alternativa descartada: `min_size>0` y capturar el fallo del arranque dejando el pool en `None` → obliga a reabrirlo a mano y agrega estados.
- `statement_cache_size` se deja por defecto: el pooler en **modo sesión** soporta prepared statements (en modo transacción no).

### D4. Migraciones con la CLI de Supabase
`npx supabase init` genera `supabase/config.toml`. Migración `supabase/migrations/<timestamp>_create_workspaces.sql` con `create table` + `insert ... on conflict (id) do nothing`. El id fijo es `00000000-0000-0000-0000-000000000001`, hardcodeado en la migración y replicado en `.env.example` (SQL de migraciones no lee variables de entorno). RLS desactivado, como indica el contrato.
- Local: `npx supabase start` y `npx supabase db reset`. Remoto: `npx supabase link --project-ref <ref>` + `npx supabase db push`; `DATABASE_URL` del pooler en modo sesión (puerto 5432).

### D5. Formato de errores
Excepción de dominio `ApiError` y handlers para: `ApiError`, `RequestValidationError`, `StarletteHTTPException` (404 → `not_found`, 405 → `not_found` conservando HTTP 405) y `Exception` (500 `internal_error`, se loguea con traza). `details` de validación: `{ "fields": [ { "field": "identity.role", "reason": "Field required" } ] }`; la ruta se arma con `loc` quitando el primer segmento (`body`/`query`/`path`); JSON inválido → `field: "body"`.

### D6. Bus de eventos
```python
class Event(BaseModel):          # sobre del contrato WS
    type: str; event_id: int | None = None; ts: datetime
    agent_id: UUID | None; task_id: UUID | None; data: dict[str, Any]

class Subscriber(Protocol):
    async def __call__(self, event: Event) -> None: ...

class EventBus:
    def subscribe(self, s: Subscriber) -> None
    async def publish(self, event: Event) -> None   # entrega en orden, aísla fallos
```
Entrega en proceso y en línea (await secuencial). La fase 2 agrega un suscriptor WebSocket (y persistencia en `task_events`) sin tocar los publicadores. `LogSubscriber` escribe `logger.info("event", extra={"event": ...})`; antes redacta `data.agent.instructions` a `"[redacted len=N]"`.
- Alternativa descartada: cola asíncrona con worker → orden y errores más difíciles de testear y no aporta nada sin WebSocket.

### D7. Logs JSON
`logging` de la stdlib con un `JsonFormatter` propio (`ts`, `level`, `logger`, `message` + extras). Sin dependencia extra. Uvicorn se configura para usar el mismo formatter.

### D8. `/health`
`db` = `Database.ping()`; `storage` = `GET {SUPABASE_URL}/storage/v1/bucket` con `Authorization: Bearer <service_role>` y `apikey`, timeout 2 s, éxito si 2xx; ambos chequeos en paralelo (`asyncio.gather`). `providers` = `{anthropic, openai, gemini}` según las keys no vacías. Cliente `httpx.AsyncClient` compartido, creado en el lifespan.

### D9. Tests
- `pytest-asyncio` en modo auto; `httpx.AsyncClient` con `ASGITransport`, ejecutando el lifespan de la app con `app.router.lifespan_context(app)` en la fixture (sin dependencia extra).
- Integración contra el Supabase local (`DATABASE_URL` de prueba). Marcador `integration`; se salta con un mensaje claro si la base no responde.
- Limpieza entre tests: fixture que hace `TRUNCATE` de las tablas de datos del test (en esta fase ninguna; `workspaces` se deja intacta porque la sembró la migración).
- Tests de contrato: validar cada respuesta con el modelo del contrato **y** comparar el conjunto exacto de llaves.

## Risks / Trade-offs

- [405 con `code: not_found`] El contrato no define código para "método no permitido" → se usa el más cercano y se conserva el HTTP 405. Si el contrato agrega uno, cambia solo el handler.
- [Id fijo duplicado en migración y `.env`] Pueden divergir → test de integración que verifica que la oficina con `DEFAULT_WORKSPACE_ID` existe.
- [Storage lento bloquea `/health`] → timeout de 2 s y chequeos en paralelo.
- [Bus en línea] Un suscriptor lento alarga la petición → aceptable con el suscriptor de log; la fase 2 decide si el WebSocket usa cola.

## Migration Plan

Proyecto nuevo, sin datos. Rollback: `npx supabase db reset` en local; en remoto, borrar la tabla `workspaces`.
