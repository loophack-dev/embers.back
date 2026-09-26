# Spec Delta

## Purpose

Unifica la forma de todos los errores REST en `{ "error": ErrorBody }`, tal como lo define el contrato oficial, para que el front los procese de una sola manera.

## ADDED Requirements

### Requirement: Forma única de error
Toda respuesta de error de la API SHALL tener el cuerpo `{ "error": { "code", "message", "details" } }`, donde `code` es un `ErrorCode` del contrato, `message` es texto en inglés y `details` es un objeto o `null`. El campo `details` MUST estar siempre presente.

#### Scenario: Error sin detalles
- **WHEN** una respuesta de error no tiene detalles
- **THEN** el cuerpo incluye `"details": null`

### Requirement: Errores de validación
Cuando la entrada de una petición no cumple el contrato (cuerpo, parámetros de ruta o de consulta, o JSON mal formado), el sistema SHALL responder HTTP 422 con `code: "validation_error"`. `details` MUST tener la forma `{ "fields": [ { "field", "reason" } ] }`, con un elemento por error; `field` es la ruta del campo con puntos (p. ej. `identity.role`), sin prefijos de framework como `body`.

#### Scenario: Falta un campo obligatorio anidado
- **WHEN** un cuerpo omite `identity.role`
- **THEN** la respuesta es 422 con `code: "validation_error"` y `details.fields` contiene un elemento con `field: "identity.role"`

#### Scenario: JSON mal formado
- **WHEN** el cuerpo no es JSON válido
- **THEN** la respuesta es 422 con `code: "validation_error"` y `details.fields` contiene un elemento con `field: "body"`

### Requirement: Ruta inexistente
Una petición a una ruta que no existe SHALL responder HTTP 404 con `code: "not_found"`.

#### Scenario: Ruta desconocida
- **WHEN** se hace `GET /does-not-exist`
- **THEN** la respuesta es 404 con `{ "error": { "code": "not_found", ... } }`

### Requirement: Método no permitido
Una petición con un método HTTP no soportado por una ruta existente SHALL responder HTTP 405 con `code: "not_found"`.

#### Scenario: Método no soportado
- **WHEN** se hace `POST /health`
- **THEN** la respuesta es 405 con `code: "not_found"`

### Requirement: Error no previsto
Una excepción no controlada SHALL responder HTTP 500 con `code: "internal_error"`, un mensaje genérico y `details: null`. La respuesta MUST NOT incluir trazas ni detalles internos; el error completo MUST quedar en el log.

#### Scenario: Excepción en un handler
- **WHEN** un handler lanza una excepción no prevista
- **THEN** la respuesta es 500 con `code: "internal_error"` y `details: null`, y el log registra la excepción
