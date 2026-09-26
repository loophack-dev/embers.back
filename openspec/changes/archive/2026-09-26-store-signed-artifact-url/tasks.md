# Tasks

## 1. Implementación

- [x] 1.1 Migración con `artifacts.url_expires_at`; `ARTIFACT_URL_TTL_S` en `Settings`/`.env.example` y quitar `PUBLIC_API_URL`; firma sin `download` en `SupabaseStorage`; `mark_ready`/`update_url` en repositorio; `ArtifactService` guarda y reutiliza la URL; `ruff` y `mypy`

## 2. Verificación y documentación

- [x] 2.1 Verificar contra el Supabase local que `artifacts.url` es la URL firmada de Storage, que descarga, que el `finish` trae la misma y que un `failed` queda nulo; actualizar contrato y README
