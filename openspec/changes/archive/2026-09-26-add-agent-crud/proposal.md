# Proposal

## Why

Con la base lista (`add-foundation`), falta el objetivo de la fase 1: que la persona pueda crear un agente con proveedor, identidad y system prompt, verlo, editarlo, darle apariencia y archivarlo, con todo persistido en Supabase y expuesto con los contratos REST oficiales.

## What Changes

- Migraciones de `agents` y `ui_settings` con la **regla de nulos** de la fase: `instructions`, `tools` y `ui_settings.data` aceptan nulo; `name`, `model_config` (con `provider` y `model_id`) e `identity` (con `role`) no. Checks sobre los jsonb, índice único parcial del nombre entre agentes activos de la oficina y trigger de `updated_at`.
- Conversión base → contrato: `instructions` nulo → `""`, `tools` nulo → `[]`, apariencia ausente o nula → `{}`, `params`, `persona` y `tone` ausentes → `null`. `params` sale como `null` si no se configuró ninguno (forma esperada por el front, alineada con el contrato). Campos de fases posteriores fijos: `character_status: "idle"`, `current_task_id: null`, `queued_task_ids: []`.
- Catálogo de proveedores en `config/providers.yaml` con los modelos vigentes (septiembre de 2026); `available` según la API key de cada proveedor.
- Catálogo de las tres herramientas del demo (`create_document`, `create_presentation`, `create_markdown`), solo registradas.
- Endpoints: `GET /providers`, `GET /tools`, `GET /agents`, `POST /agents`, `GET /agents/{id}`, `PATCH /agents/{id}`, `DELETE /agents/{id}`, `PUT /agents/{id}/appearance`, con las reglas de negocio de la sección 5 del documento de fase.
- Publicación de `agent.created`, `agent.updated` y `agent.archived` en el bus interno.
- Sin tests automatizados (decisión del usuario): la verificación es manual con `curl` contra el Supabase local.

### Catálogo de modelos propuesto

| Proveedor | id | label |
|---|---|---|
| anthropic | `claude-fable-5-1` | Claude Fable 5.1 |
| anthropic | `claude-opus-5-5` | Claude Opus 5.5 |
| anthropic | `claude-sonnet-5` | Claude Sonnet 5 |
| anthropic | `claude-haiku-4-5` | Claude Haiku 4.5 |
| openai | `gpt-6-astra` | GPT-6 Astra |
| openai | `gpt-5.6-terra` | GPT-5.6 Terra |
| openai | `gpt-5.6-luna` | GPT-5.6 Luna |
| gemini | `gemini-3.8-flash` | Gemini 3.8 Flash |
| gemini | `gemini-3.5-flash-lite` | Gemini 3.5 Flash-Lite |
| gemini | `gemini-3.1-pro-preview` | Gemini 3.1 Pro (preview) |

### Precisiones que los documentos no definen (a aprobar)

1. **PATCH con `null`**: `name`, `model_config` o `identity` en `null` → `validation_error`. `instructions: null` equivale a `""` y `tools: null` equivale a `[]` (ambos se guardan como nulo), porque el contrato los admite como `null` en `AgentUpdate`.
2. **Cuándo sube `version`**: solo si el valor enviado es distinto del guardado (comparado en la forma del contrato). Un PATCH sin cambios reales responde 200 con el agente, no escribe, no sube `version` y no publica evento.
3. **Nulos en `AgentCreate`**: `instructions: null` y `tools: null` → `validation_error`, porque el contrato no los define como anulables en la creación. `appearance: null` equivale a no enviarla.
4. **Herramientas repetidas**: se eliminan los duplicados conservando el orden.
5. **Tamaño de la apariencia**: se mide como bytes UTF-8 del JSON serializado; más de 65.536 bytes → `validation_error` en `data` (PUT) o `appearance` (POST).
6. **Nombre**: comparación exacta (sensible a mayúsculas). Duplicado entre activos → `validation_error` en `name`, tanto en POST como en PATCH.
7. **Orden de errores**: 422 de forma → 404 → 409 `agent_archived` → 422 de catálogo (`model_id`, luego `unknown_tool`) → 422 de nombre duplicado.
8. **DELETE**: agente inexistente → 404 `not_found`; ya archivado → 204 sin volver a publicar `agent.archived`.
9. **Id inválido en la ruta** (no UUID) → 422 `validation_error` en `id`.
10. **Campos desconocidos en los cuerpos** → `validation_error` (`extra="forbid"`), salvo dentro de la apariencia, que es libre.

## Capabilities

### New Capabilities
- `agents`: persistencia del agente, regla de nulos, conversión al contrato y los seis endpoints de `/agents`, con sus eventos.
- `catalogs`: catálogos de proveedores/modelos y de herramientas, y sus endpoints `GET /providers` y `GET /tools`.

### Modified Capabilities
- `app-config`: CORS acepta cualquier origen por defecto (`CORS_ORIGINS=*`), a pedido del usuario por problemas de CORS con el front.

## Impact

- Nuevas migraciones en `supabase/migrations/`, `config/providers.yaml`, módulos en `src/embers/{contracts,domain,db,api/routes}`.
- Nueva dependencia: `pyyaml` (y `types-pyyaml` para mypy).
- API pública nueva: los ocho endpoints listados.
