# Spec Delta

## MODIFIED Requirements

### Requirement: CORS configurable
El sistema SHALL permitir peticiones de origen cruzado desde cualquier origen por defecto. `CORS_ORIGINS` MUST aceptar `*` (valor por defecto, también cuando está vacía o ausente) para permitir cualquier origen, o una lista separada por comas para restringirlos.

#### Scenario: Cualquier origen por defecto
- **WHEN** `CORS_ORIGINS` no está definida o vale `*` y llega una petición preflight desde cualquier origen
- **THEN** la respuesta incluye `Access-Control-Allow-Origin: *`

#### Scenario: Origen no permitido
- **WHEN** `CORS_ORIGINS=http://localhost:5173` y llega una petición desde otro origen
- **THEN** la respuesta no incluye `Access-Control-Allow-Origin`

#### Scenario: Origen permitido
- **WHEN** `CORS_ORIGINS=http://localhost:5173` y llega una petición preflight desde `http://localhost:5173`
- **THEN** la respuesta incluye `Access-Control-Allow-Origin: http://localhost:5173`
