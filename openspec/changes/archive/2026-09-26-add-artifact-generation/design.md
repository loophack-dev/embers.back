# Design

## Context

`add-agent-execution` dejó `StrandsRuntime` con un registro vacío `TOOL_FACTORIES` y `TaskService._finish` con `artifacts=[]`. `app.state.http` (httpx) ya existe y `/health` ya llama a Storage con la service role key. Alcance y precisiones: proposal.md.

## Goals / Non-Goals

**Goals:** la generación de archivos y la subida no dependen de Strands (se reutilizan desde el runtime falso); `strands` sigue importándose solo en `runtime/strands_runtime.py`.

**Non-Goals:** otros formatos, versiones de archivos, regenerar desde `source_spec` (queda guardado para después).

## Decisions

### D1. Capas

```
runtime/strands_runtime.py  ── @tool wrappers ──┐
runtime/fake.py  ───────────────────────────────┤
                                                ▼
domain/artifacts.py (ArtifactService: create_* → registro, genera, sube, ready/failed; ready_for_task; signed_url)
   ├─ artifacts/specs.py      DocumentSpec, PresentationSpec, MarkdownSpec (Pydantic, límites)
   ├─ artifacts/generators.py build_docx / build_pptx / build_markdown → bytes   (python-docx, python-pptx)
   ├─ domain/ports.py         ArtifactRepository, FileStorage (Protocols)
   ├─ db/artifacts_repository.py
   └─ storage/supabase_storage.py (httpx: upload, sign)
api/routes/artifacts.py  GET /artifacts/{id}/download → ArtifactService.signed_url → 302
```

### D2. Herramientas en Strands
`build_artifact_tools(service, request)` crea, por tarea, tres funciones `@tool` asíncronas con parámetros tipados con los modelos de `artifacts/specs.py` aplanados (`title`, `summary`, `sections: list[Section]`…). Strands genera el JSON Schema desde las anotaciones. Cada wrapper llama `ArtifactService.create_*(task_id, agent_id, spec)` y devuelve texto: `"Created docx '<title>' (id <uuid>)."` o `"Error: <motivo>"`. Se registran en `StrandsRuntime` según `tools` del snapshot (reemplaza `TOOL_FACTORIES`).

### D3. Validación antes del registro
`ArtifactService.create_*` recibe un `dict` y valida con `DocumentSpec`/`PresentationSpec`/`MarkdownSpec`; un `ValidationError` se devuelve como texto al modelo sin tocar la base (proposal, precisión 1). Límites: título ≤ 200; documento 1–30 secciones; presentación 1–20 slides, ≤ 6 viñetas por slide; markdown ≤ 100.000 caracteres.

### D4. Generación
- docx: `Document()`, `add_heading(title, 0)`, resumen como párrafo, por sección `add_heading(level=1)`, párrafos, viñetas con estilo `List Bullet`, tabla con estilo `Table Grid`.
- pptx: `Presentation(PPTX_TEMPLATE_PATH)` o `Presentation()`; portada con layout 0 (título + subtítulo); contenido con layout 1 (título + cuerpo con viñetas); notas en `notes_slide.notes_text_frame`. Si la plantilla no tiene esos layouts, se usa el primero disponible y se escribe en los placeholders que existan.
- md: `# {title}\n\n{content}\n`.
- La generación es CPU y rápida; corre con `asyncio.to_thread` para no bloquear el loop.

### D5. Storage
`SupabaseStorage` con el `httpx.AsyncClient` compartido y la service role key:
- Subida: `POST {SUPABASE_URL}/storage/v1/object/{bucket}/{path}` con `Content-Type` = mime y `x-upsert: true`.
- Firma: `POST {SUPABASE_URL}/storage/v1/object/sign/{bucket}/{path}` con `{"expiresIn": ttl}` → `signedURL` relativo; `download_url = SUPABASE_URL + "/storage/v1" + signedURL + "&download=<título>.<ext>"`.
- Bucket: migración `insert into storage.buckets (id, name, public) values ('artifacts', 'artifacts', false) on conflict (id) do nothing`, así local y remoto quedan iguales con `db reset`/`db push`.

### D6. Finish y `artifact_error`
`TaskService` recibe un puerto `TaskArtifacts` (`ready_for_task(task_id) -> list[ArtifactOut]`, implementado por `ArtifactService`). En `Completed`: lee los `ready`; si `expected_output` y ninguno es de ese tipo → `finish` `failed` con `artifact_error` y el `result_text` del agente. En cualquier `finish` (también los fallidos), `artifacts` lleva los `ready` que existan.

### D7. Runtime falso
Recibe el `ArtifactService`. Si `expected_output` existe, después de la espera genera un archivo mínimo del tipo pedido (título "Entregable de prueba", una sección/slide con la instrucción) y luego devuelve `Completed`.

## Risks / Trade-offs

- [JSON Schema anidado en Strands] Si algún proveedor rechaza el schema de listas de objetos → las specs están en un solo módulo; se aplanaría la entrada.
- [URL firmada local] Apunta a `127.0.0.1:54321`, válida solo en la máquina local → en remoto usa la URL del proyecto.
- [Plantilla sin layouts estándar] Se degrada al primer layout; se documenta en el README.

## Migration Plan

`npx supabase db reset` en local; `npx supabase db push` en remoto (crea tabla y bucket). Rollback: `drop table artifacts` y borrar el bucket desde Studio.
