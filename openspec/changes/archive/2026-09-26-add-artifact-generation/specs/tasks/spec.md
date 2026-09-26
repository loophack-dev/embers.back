# Spec Delta

## ADDED Requirements

### Requirement: Artefactos en el finish
El `finish` de una tarea SHALL incluir en `artifacts` todos los archivos `ready` de la tarea, en orden de creación y en la forma `ArtifactOut`, cada uno con `download_url` firmada nueva y su `url_expires_at`.

#### Scenario: Varios archivos
- **WHEN** el agente genera un documento y un markdown en la misma tarea
- **THEN** el `finish` trae ambos en `artifacts`, cada uno con `download_url` y `url_expires_at`

### Requirement: Archivo esperado no entregado
Si la tarea trae `expected_output` y al terminar el agente no hay ningún artefacto `ready` de ese tipo, la tarea SHALL terminar `failed` con `error.code: "artifact_error"`, conservando el `result_text` del agente y los artefactos `ready` que sí existan.

#### Scenario: Pidió pptx y no lo generó
- **WHEN** la tarea pide `expected_output: "pptx"` y el agente termina sin crear una presentación
- **THEN** llega `finish` `failed` con `error.code: "artifact_error"` y el `result_text` del agente
