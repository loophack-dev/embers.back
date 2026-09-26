# Tasks

## 1. Implementación

- [x] 1.1 Migración con la columna `artifacts.url`; `PUBLIC_API_URL` en `Settings` y `.env.example`; `mark_ready` y `ArtifactService` guardan la URL; verificar con `npx supabase db reset`, `ruff` y `mypy`

## 2. Verificación y documentación

- [x] 2.1 Verificar a mano con el runtime falso que un archivo `ready` guarda la URL, que abrirla redirige y descarga, y que un archivo `failed` queda con `url` nulo; actualizar contrato y README (incluido el `update` para dominios que cambian)
