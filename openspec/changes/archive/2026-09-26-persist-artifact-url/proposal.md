# Proposal

## Why

El front necesita leer de la base una URL de cada archivo generado para mostrarlo. Hoy la base no guarda ninguna URL: `download_url` solo viaja en el `finish` y es firmada, así que vence a la hora.

## What Changes

- Columna **`artifacts.url`** (`text`, nula mientras el archivo no está `ready`).
- Al quedar `ready`, el backend guarda `url = {PUBLIC_API_URL}/artifacts/{id}/download`. Es una URL **estable**: no vence, porque el endpoint redirige cada vez a una URL firmada nueva. El bucket sigue privado.
- Variable nueva **`PUBLIC_API_URL`** (por defecto `http://localhost:3523`): la URL pública del backend (p. ej. el túnel o el dominio de producción).
- `finish.artifacts[].download_url` no cambia: sigue siendo la URL firmada del contrato.
- Contrato actualizado con la columna nueva.

### Precisiones a aprobar

1. **Si cambia `PUBLIC_API_URL`** (p. ej. un túnel `trycloudflare` que se reinicia), las URLs ya guardadas quedan con el dominio anterior. Se corrigen con un `update` en SQL (queda en el README). Para producción conviene un dominio fijo.
2. **Archivos existentes**: la migración no puede conocer `PUBLIC_API_URL`, así que no rellena los `ready` anteriores; el README trae el `update` para hacerlo.
3. **Lectura desde el front**: la tabla `artifacts` no se publica en Realtime en este change. Si el front la va a consultar directo en Supabase, aplica la misma advertencia de RLS desactivado.

## Capabilities

### New Capabilities
- Ninguna.

### Modified Capabilities
- `artifacts`: la URL estable de cada archivo listo queda guardada en la base.

## Impact

- Una migración, `config.py`, `db/artifacts_repository.py`, `domain/artifacts.py`, `.env.example`, contrato y README. Sin tests automatizados.
