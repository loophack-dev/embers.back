# Spec Delta

## Purpose

Expone el estado del backend y de sus dependencias (Postgres, Storage de Supabase y proveedores de modelos) con el contrato `HealthOut`.

## ADDED Requirements

### Requirement: Endpoint de salud
`GET /health` SHALL responder HTTP 200 con un objeto `HealthOut` que tiene exactamente los campos `status`, `db`, `storage` y `providers`, aunque alguna dependencia falle.

#### Scenario: Forma de la respuesta
- **WHEN** se hace `GET /health`
- **THEN** la respuesta es 200 y el cuerpo tiene exactamente `status`, `db`, `storage` y `providers`, sin campos adicionales

### Requirement: Estado según la base
`db` SHALL ser `true` si una consulta a Postgres responde en menos de 2 segundos. `status` MUST ser `ok` si `db` es `true` y `degraded` en caso contrario, independientemente de `storage` y `providers`.

#### Scenario: Base disponible
- **WHEN** Postgres responde
- **THEN** `db` es `true` y `status` es `ok`

#### Scenario: Base no disponible
- **WHEN** Postgres no responde
- **THEN** `db` es `false` y `status` es `degraded`

### Requirement: Estado de Storage
`storage` SHALL ser `true` si la API de Storage de Supabase responde con éxito en menos de 2 segundos usando la service role key, y `false` en caso contrario.

#### Scenario: Storage caído no degrada
- **WHEN** Postgres responde y Storage no
- **THEN** `storage` es `false` y `status` sigue siendo `ok`

### Requirement: Proveedores configurados
`providers` SHALL ser un objeto con exactamente las llaves `anthropic`, `openai` y `gemini`, cada una con un booleano que indica si su API key (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`) está configurada y no vacía. La respuesta MUST NOT incluir el valor de ninguna key.

#### Scenario: Solo una key configurada
- **WHEN** solo `OPENAI_API_KEY` tiene valor
- **THEN** `providers` es `{ "anthropic": false, "openai": true, "gemini": false }`
