# Spec Delta

## ADDED Requirements

### Requirement: URL estable guardada
Cuando un artefacto queda `ready`, el sistema SHALL guardar en `artifacts.url` la URL `{PUBLIC_API_URL}/artifacts/{id}/download`, que no vence. Mientras el artefacto está `generating` o si queda `failed`, `url` MUST ser nulo.

#### Scenario: Archivo listo
- **WHEN** el agente genera un archivo que queda `ready`
- **THEN** `artifacts.url` es `{PUBLIC_API_URL}/artifacts/<id>/download` y abrirla redirige (302) a una URL firmada que descarga el archivo

#### Scenario: Archivo fallido
- **WHEN** la generación o la subida fallan
- **THEN** `artifacts.url` queda nulo
