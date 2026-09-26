# Proposal

## Why

El agente ya trabaja con Strands, pregunta y entrega texto, pero todavía no genera los archivos que pide la persona. Falta el resultado visible del demo: documentos Word, presentaciones PowerPoint y archivos Markdown guardados en Supabase Storage y entregados en el `finish` con una URL de descarga.

## What Changes

- Migración de **`artifacts`** con la regla de nulos de la fase 2 (no nulos: `id`, `workspace_id`, `task_id`, `agent_id`, `type`, `status`, `created_at`; el resto acepta nulo) y checks de `type` y `status`. Creación del **bucket privado `artifacts`** en la misma migración.
- Herramientas **`create_document`**, **`create_presentation`** y **`create_markdown`**, disponibles si están en `tools` del agente:
  - Entrada estructurada con límites: documento con título, resumen opcional y hasta **30 secciones** (encabezado, párrafos, viñetas y tabla opcional); presentación con título, subtítulo opcional y hasta **20 slides** (título, hasta **6 viñetas**, notas); markdown con título y contenido.
  - Registro en `generating`, generación con python-docx, python-pptx o texto, subida a Storage en `{workspace_id}/{task_id}/{artifact_id}.{ext}`, paso a `ready` y respuesta al modelo con id, título y tipo.
  - Si falla, registro en `failed` con `error` y el error como respuesta de la herramienta, para que el modelo decida si reintenta.
- Plantilla `.pptx` opcional con `PPTX_TEMPLATE_PATH`.
- **URLs firmadas** con `SIGNED_URL_TTL_S` (3.600 s) y **`GET /artifacts/{id}/download`**: 302 a una URL firmada nueva; `not_found` si no existe o no está `ready`.
- **`finish.artifacts`**: todos los archivos `ready` de la tarea en la forma `ArtifactOut`, con URL firmada nueva.
- **`artifact_error`**: si la tarea trae `expected_output` y al terminar no hay ningún archivo `ready` de ese tipo, `finish` fallido con `artifact_error` y el `result_text` que haya.
- Dependencias nuevas: `python-docx` y `python-pptx`. Variables nuevas: `ARTIFACTS_BUCKET`, `SIGNED_URL_TTL_S`, `PPTX_TEMPLATE_PATH`.

### Precisiones que los documentos no definen (a aprobar)

1. **Entrada inválida de una herramienta** (p. ej. 21 slides o 7 viñetas): se rechaza **antes** de crear el registro y se le responde al modelo con el motivo, para que corrija. No queda fila `failed`: `failed` se reserva para fallos de generación o de subida.
2. **Runtime falso con `expected_output`**: para que siga sirviendo como plan B del demo, genera un archivo mínimo del tipo pedido (título fijo y el texto de la instrucción) usando las mismas herramientas; sin `expected_output` no genera nada.
3. **URL firmada**: `download_url` es absoluta (`{SUPABASE_URL}/storage/v1/object/sign/...`) y `url_expires_at` = momento de firma + `SIGNED_URL_TTL_S`. Con Supabase local la URL apunta a `127.0.0.1:54321`.
4. **Formato de la tabla del documento**: `headers` (lista de textos) y `rows` (lista de filas de textos); se usa el estilo "Table Grid" de python-docx.
5. **Nombre del archivo descargado**: la URL firmada lleva el parámetro `download=<título>.<ext>` de Supabase Storage, para que la descarga tenga un nombre legible en vez del id.
6. **`ArtifactOut.title`** no acepta nulo en el contrato: las herramientas siempre guardan el título que da el modelo (obligatorio en su entrada).
7. **Límites de texto**: título hasta 200 caracteres; contenido markdown hasta 100.000 caracteres.

## Capabilities

### New Capabilities
- `artifacts`: tabla, bucket, herramientas de archivos, subida, URLs firmadas y descarga.

### Modified Capabilities
- `agent-runtime`: las herramientas de archivos quedan implementadas; el runtime falso genera el archivo pedido.
- `tasks`: `finish.artifacts` real y la regla de `artifact_error`.

## Impact

- Nuevos módulos: `artifacts/` (generadores docx/pptx/md, sin Strands), `storage/` (cliente de Supabase Storage con `httpx`), `domain/artifacts.py`, `db/artifacts_repository.py`, `api/routes/artifacts.py`. Los wrappers `@tool` viven en `runtime/strands_runtime.py`.
- Sin tests automatizados (decisión del usuario): se verifica abriendo los archivos generados con python-docx y python-pptx a mano.
