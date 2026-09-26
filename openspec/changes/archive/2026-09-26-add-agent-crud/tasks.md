# Tasks

## 1. Base de datos

- [x] 1.1 Crear la migración de `agents` (columnas, checks jsonb, índice único parcial del nombre, índice por creación, función y trigger `set_updated_at`); verificar con `npx supabase db reset` que aplica limpia
- [x] 1.2 Crear la migración de `ui_settings` (checks, unicidad compuesta, trigger); verificar con `npx supabase db reset` y con un `insert` manual sin `role` que la base lo rechaza
- [x] 1.3 Registrar el codec `jsonb` en el `init` del pool de `Database`; verificar que `ruff` y `mypy` pasan

## 2. Contratos y catálogos

- [x] 2.1 Implementar `contracts/agents.py` y `contracts/catalogs.py` (entradas con `extra="forbid"`, rechazo de `null` en `name`/`model_config`/`identity` del PATCH, `ItemsOut`); verificar con `mypy`
- [x] 2.2 Crear `config/providers.yaml` con el catálogo aprobado, agregar `pyyaml` + `types-pyyaml`, `PROVIDERS_FILE` opcional en `Settings` y `.env.example`, e implementar `domain/catalogs.py` (`ProviderCatalog`, `TOOL_CATALOG`); verificar que carga en el arranque
- [x] 2.3 Implementar `api/routes/catalogs.py` (`GET /providers`, `GET /tools`) y montarlo; verificar con `curl` la forma `{ items }` y `available` según las keys

## 3. Agentes

- [x] 3.1 Implementar `domain/ports.py` (`AgentRepository`, `AgentRecord`) y `db/agents_repository.py` (crear con apariencia en transacción, obtener, listar, actualizar, archivar, guardar apariencia; errores de unicidad y check mapeados)
- [x] 3.2 Implementar `domain/agents.py` (`AgentService`: conversión a `AgentOut`, validación de catálogo y herramientas, normalización de nulos, cálculo de `version`, tamaño de apariencia, publicación de eventos tras el commit)
- [x] 3.3 Implementar `api/routes/agents.py` con los seis endpoints y montarlo; verificar que `ruff` y `mypy` pasan

## 4. Verificación y documentación

- [x] 4.1 Recorrer con `curl` contra el Supabase local los criterios CA1–CA11 y los escenarios de las specs (incluidos los errores), revisando el log de eventos
- [x] 4.2 Actualizar `README.md` con los endpoints y ejemplos de uso; verificar que `ruff check`, `ruff format --check` y `mypy src` pasan
