# Design

## Context

`ArtifactService.create` marca el artefacto `ready` con `storage_path` y `size_bytes`; `GET /artifacts/{id}/download` ya redirige a una URL firmada nueva. Ver proposal.md.

## Decisions

- **D1.** `mark_ready` recibe también `url`; `ArtifactService` la arma con `PUBLIC_API_URL` (sin `/` final). Una sola escritura: `ready`, `storage_path`, `size_bytes` y `url` quedan juntos.
- **D2.** Se guarda la URL absoluta (elección del usuario) y no una ruta relativa: el front la usa tal cual. El costo es reescribirla si cambia el dominio (proposal, precisión 1).
- **D3.** `ArtifactOut` no cambia: el contrato sigue entregando la URL firmada en `download_url`.

## Risks / Trade-offs

- [Dominio cambiante] URLs viejas apuntan al dominio anterior → `update artifacts set url = replace(url, '<viejo>', '<nuevo>')`.
