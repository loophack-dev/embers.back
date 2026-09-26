# Proposal

## Why

El front necesita la URL firmada de Supabase Storage del archivo (`https://<ref>.supabase.co/storage/v1/object/sign/artifacts/...?token=...`), no un enlace al backend. `persist-artifact-url` guardaba `{PUBLIC_API_URL}/artifacts/{id}/download`, que obliga a exponer el backend.

## What Changes

- `artifacts.url` guarda la **URL firmada de Supabase Storage**, con la misma forma que genera Supabase (sin parámetros extra), al quedar el archivo `ready`.
- Columna nueva **`artifacts.url_expires_at`**: vencimiento de esa URL.
- Variable nueva **`ARTIFACT_URL_TTL_S`** (por defecto **604.800 s = 7 días**, igual que el ejemplo del usuario).
- `finish.artifacts[].download_url` y `url_expires_at` usan la URL guardada; si ya venció, se firma una nueva y se actualiza la base.
- Se elimina `PUBLIC_API_URL` (ya no se usa). `GET /artifacts/{id}/download` no cambia (sigue redirigiendo a una URL firmada nueva de `SIGNED_URL_TTL_S`).

### Precisiones

1. **La URL guardada vence** a los 7 días. Pasado ese plazo, la base conserva la URL vencida hasta que algo la renueve (un nuevo `finish` no aplica a tareas terminadas). Para una vigencia mayor se sube `ARTIFACT_URL_TTL_S`.
2. Con Supabase local la URL apunta a `http://127.0.0.1:54321`; con el remoto, a `https://<ref>.supabase.co`.

## Capabilities

### Modified Capabilities
- `artifacts`: la URL guardada pasa a ser la firmada de Storage, con su vencimiento.

## Impact

- Una migración (`url_expires_at`), `config.py`, `storage/supabase_storage.py`, `db/artifacts_repository.py`, `domain/artifacts.py`, `main.py`, `.env.example`, contrato y README. Sin tests automatizados.
