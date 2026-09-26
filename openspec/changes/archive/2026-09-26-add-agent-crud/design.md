# Design

## Context

Construye sobre `add-foundation` (specs en `openspec/specs/`): `create_app` con `app.state` (`settings`, `db`, `bus`, `http`), dependencias tipadas en `api/deps.py`, `ApiError` + handlers con la forma `{ "error": ... }` y `EventBus` con `LogSubscriber`. El criterio CA2 (`/health` en `ok`) ya lo cubre la spec `health`.

## Goals / Non-Goals

**Goals:**
- Reglas de negocio en `domain/`, sin FastAPI ni asyncpg. SQL solo en `db/`. HTTP solo en `api/`.
- Una sola función que convierte fila → `AgentOut` (regla de nulos en un único lugar).

**Non-Goals:**
- Tareas, `character_status` real, WebSocket, memoria.
- Tests automatizados (decisión del usuario).

## Decisions

### D1. Capas

```
api/routes/agents.py ──► domain/agents.py (AgentService) ──► domain/ports.py (AgentRepository: Protocol)
api/routes/catalogs.py ─► domain/catalogs.py (ProviderCatalog, TOOL_CATALOG)          ▲
                                                                                        │ implementa
                                                            db/agents_repository.py (asyncpg)
contracts/agents.py, contracts/catalogs.py: modelos Pydantic del contrato (entrada y salida)
```
- `AgentService` recibe el repositorio, los catálogos y el `EventBus`; lanza `ApiError`. Se construye por petición en `api/deps.py`.
- Alternativa descartada: lógica en las rutas → mezcla HTTP con reglas y duplica validaciones entre POST y PATCH.

### D2. Modelos del contrato
- Entrada con `extra="forbid"`: `ModelParams`, `ModelConfig`, `AgentIdentity`, `AgentCreate`, `AgentUpdate`, `AppearanceUpdate`. `appearance`/`data` son `dict[str, Any]` libres.
- `AgentUpdate`: para distinguir "no enviado" de `null` se usa `model_fields_set`. Un `model_validator` rechaza `null` en `name`, `model_config`, `identity`.
- Salida: `AgentOut`, `ProviderOut`, `ProviderModelOut`, `ToolOut`, `ItemsOut[T]` (`{ items }`). `ModelConfig`/`AgentIdentity` de salida siempre con todas sus llaves (`params` completo, `persona`/`tone` en `null`).
- `Provider` sin `bedrock` (desviación aprobada en `add-foundation`).

### D3. Migraciones
Dos archivos nuevos en `supabase/migrations/`:
- `agents`: columnas de la sección 3 del documento de fase; `workspace_id` con default `'00000000-0000-0000-0000-000000000001'` y FK `on delete cascade`; checks: `char_length(name) between 1 and 60`, `instructions` ≤ 8000, `status in ('active','archived')`, `jsonb_typeof(model_config)='object' and model_config ? 'provider' and model_config ? 'model_id'`, `jsonb_typeof(identity)='object' and identity ? 'role'`; índice único parcial `(workspace_id, name) where status = 'active'`; índice `(workspace_id, created_at)`; función `set_updated_at()` + trigger `before update`.
- `ui_settings`: columnas de la sección 3; checks `owner_type in ('workspace','agent')`, `data is null or jsonb_typeof(data)='object'`, `data is null or octet_length(data::text) <= 65536`; `unique (workspace_id, owner_type, owner_id, namespace)`; trigger de `updated_at`. `owner_id` sin FK (es polimórfico).

### D4. Repositorio (asyncpg)
SQL parametrizado (`$1..$n`); jsonb con codec `json` registrado en el `init` del pool (se agrega a `Database`). Lecturas con `LEFT JOIN ui_settings` (namespace `appearance`, owner_type `agent`). Creación de agente + apariencia en una transacción. Apariencia con `INSERT ... ON CONFLICT (...) DO UPDATE`. Unicidad del nombre: se captura `UniqueViolationError` del índice parcial → `ApiError(validation_error, field=name)`; `CheckViolationError` de `ui_settings.data` → `validation_error`.
- Alternativa descartada: `SELECT` previo para el nombre → carrera entre dos creaciones.

### D5. Versión y cambios
El servicio arma el agente "después" en la forma del contrato y compara campo a campo con el "antes": si difieren `model_config`, `identity`, `instructions` o `tools` → `version + 1`; si no hay ninguna diferencia → no escribe ni publica. La normalización (`""`/`null` en `instructions`, `[]`/`null` en `tools`) se hace antes de comparar.

### D6. Catálogo de proveedores
`config/providers.yaml` leído una vez en el lifespan (`ProviderCatalog.from_yaml`), guardado en `app.state.providers`. Ruta configurable con `PROVIDERS_FILE` (por defecto `config/providers.yaml`), opcional. `available` se calcula con `Settings` en cada `GET /providers`. Herramientas: constante `TOOL_CATALOG` en `domain/catalogs.py` (no cambian sin código de fase 3).

### D7. Eventos
El servicio publica después del `commit` con `Event(type, ts=now UTC, agent_id, task_id=None, data)`. `data.agent` = `AgentOut.model_dump(mode="json")`.

### D8. Tamaño de la apariencia
`len(json.dumps(data, ensure_ascii=False).encode("utf-8")) > 65536` → `validation_error`. Con los separadores por defecto (`", "`, `": "`) coincide con la salida de `jsonb::text`, así que el check de la base no rechaza lo que la API aceptó.

## Risks / Trade-offs

- [Modelos del catálogo cambian rápido] → están en YAML; cambiar el archivo y reiniciar.
- [`claude-haiku-4-5` es alias] → Anthropic lo resuelve a la versión fechada; se revisa en la fase 3 al llamar al modelo.
- [Sin tests automatizados] → regresiones solo detectables a mano; la tarea final corre un recorrido `curl` que cubre los 11 criterios.

## Migration Plan

`npx supabase db reset` en local; `npx supabase db push` en remoto. Rollback: `drop table ui_settings, agents` y la función `set_updated_at`.
