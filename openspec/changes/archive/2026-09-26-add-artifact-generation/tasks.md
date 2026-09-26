# Tasks

## 1. Base de datos, Storage y configuración

- [x] 1.1 Crear la migración de `artifacts` (regla de nulos, checks) y del bucket privado `artifacts`; verificar con `npx supabase db reset` que la tabla y el bucket existen
- [x] 1.2 Agregar `python-docx` y `python-pptx`; `ARTIFACTS_BUCKET`, `SIGNED_URL_TTL_S` y `PPTX_TEMPLATE_PATH` en `Settings` y `.env.example`; verificar con `uv sync` y `mypy`

## 2. Generación y almacenamiento

- [x] 2.1 Implementar `artifacts/specs.py` (límites) y `artifacts/generators.py` (docx, pptx con plantilla opcional, md); verificar a mano abriendo los archivos generados con python-docx y python-pptx
- [x] 2.2 Implementar `storage/supabase_storage.py` (subida y firma), `db/artifacts_repository.py` y `domain/artifacts.py` (`ArtifactService`); verificar a mano una subida y una URL firmada que descarga el archivo

## 3. Integración con tareas y runtimes

- [x] 3.1 Registrar las herramientas `@tool` en `StrandsRuntime` según `tools` y verificar con un modelo guionado (sin red) que se crean los tres tipos y que una entrada inválida no crea registro
- [x] 3.2 `TaskService`: `finish.artifacts` real y regla de `artifact_error`; runtime falso con `expected_output`
- [x] 3.3 Implementar `GET /artifacts/{id}/download` (302 o 404) y montarlo

## 4. Verificación y documentación

- [x] 4.1 Verificar a mano con `AGENT_RUNTIME=fake`: `finish` con artefactos pptx, docx y md (CA7, CA8), descarga por `download_url` y por `/artifacts/{id}/download` (CA9), y los archivos abren con python-docx/python-pptx
- [x] 4.2 Actualizar `README.md` (herramientas, Storage, descarga, plantilla); `ruff` y `mypy` sin errores
