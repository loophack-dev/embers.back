# artifacts Specification

## Purpose
Genera los archivos que entrega el agente (docx, pptx y md), los guarda en Supabase Storage y los expone con URLs firmadas.

## Requirements

### Requirement: Tabla y bucket de artefactos
Las migraciones SHALL crear `artifacts` según la sección 3 del documento de fase 2, con la regla de nulos (no nulos: `id`, `workspace_id`, `task_id`, `agent_id`, `type`, `status`, `created_at`), `type` en `docx`, `pptx` o `md` y `status` en `generating`, `ready` o `failed`, y el bucket **privado** `artifacts` en Supabase Storage.

#### Scenario: Migración sobre base vacía
- **WHEN** se aplican las migraciones sobre un Supabase vacío
- **THEN** existen la tabla `artifacts` y el bucket `artifacts` con acceso privado

### Requirement: Herramientas de archivos
Cuando el agente tiene la herramienta en `tools`, SHALL poder usar: `create_document` (título, resumen opcional, de 1 a 30 secciones con encabezado, párrafos, viñetas y tabla opcional), `create_presentation` (título, subtítulo opcional, de 1 a 20 slides con título, hasta 6 viñetas y notas; genera una slide de portada más las de contenido) y `create_markdown` (título y contenido). Una entrada que no cumple los límites MUST rechazarse sin crear registro, respondiendo al modelo el motivo.

#### Scenario: Presentación con demasiadas slides
- **WHEN** el modelo llama `create_presentation` con 21 slides
- **THEN** la herramienta responde el error de límite y no se crea ningún registro en `artifacts`

### Requirement: Generación y subida
Cada herramienta SHALL crear el registro en `generating` (con `title`, `type`, `mime` y `source_spec`), generar el archivo, subirlo a Storage en `{workspace_id}/{task_id}/{artifact_id}.{ext}`, marcarlo `ready` con `storage_path` y `size_bytes`, y responder al modelo el `id`, el título y el tipo. Si la generación o la subida fallan, MUST marcarlo `failed` con `error` y responder el error al modelo.

#### Scenario: Archivo listo
- **WHEN** el agente genera un documento válido
- **THEN** la fila queda `ready` con `storage_path` y `size_bytes`, y el objeto existe en el bucket

#### Scenario: Falla la subida
- **WHEN** Storage no acepta el archivo
- **THEN** la fila queda `failed` con `error` y el modelo recibe el error

### Requirement: Contenido de los archivos
El `.docx` SHALL tener el título como encabezado principal, el resumen si existe y cada sección con su encabezado, párrafos, viñetas y tabla. El `.pptx` MUST tener una slide de portada con título y subtítulo y una slide por cada slide pedida, con sus viñetas y notas; si `PPTX_TEMPLATE_PATH` apunta a un `.pptx`, MUST usarse como plantilla. El `.md` MUST empezar con `# <título>` seguido del contenido.

#### Scenario: CA7 · Presentación
- **WHEN** se envía `delegate` con `expected_output: "pptx"` y el agente crea una presentación de 4 slides
- **THEN** el `finish` trae un artefacto `pptx` `ready` cuyo `download_url` descarga un archivo que python-pptx abre con 5 slides (portada + 4) y los títulos pedidos

#### Scenario: CA8 · Documento y markdown
- **WHEN** se piden `expected_output: "docx"` y `expected_output: "md"`
- **THEN** cada `finish` trae su artefacto; el `.docx` abre con python-docx con el título y las secciones, y el `.md` empieza con `# <título>`

### Requirement: Descarga
`GET /artifacts/{id}/download` SHALL responder 302 a una URL firmada nueva, vigente por `SIGNED_URL_TTL_S` segundos (por defecto 3.600). Si el artefacto no existe o no está `ready`, MUST responder 404 `not_found`.

#### Scenario: CA9 · Redirección a URL vigente
- **WHEN** se hace `GET /artifacts/{id}/download` de un artefacto `ready`
- **THEN** la respuesta es 302 con `Location` a una URL firmada que descarga el archivo

#### Scenario: Artefacto no listo
- **WHEN** el artefacto está `failed` o no existe
- **THEN** la respuesta es 404 con `code: "not_found"`
