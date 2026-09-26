# Spec Delta

## MODIFIED Requirements

### Requirement: URL estable guardada
Cuando un artefacto queda `ready`, el sistema SHALL guardar en `artifacts.url` la URL firmada de Supabase Storage del archivo (`{SUPABASE_URL}/storage/v1/object/sign/{bucket}/{storage_path}?token=...`), vigente por `ARTIFACT_URL_TTL_S` segundos (por defecto 604.800), y su vencimiento en `artifacts.url_expires_at`. Mientras el artefacto está `generating` o si queda `failed`, `url` y `url_expires_at` MUST ser nulos. El `finish` MUST entregar esa URL guardada en `download_url`; si ya venció, MUST firmarse una nueva y actualizar la base.

#### Scenario: Archivo listo
- **WHEN** el agente genera un archivo que queda `ready`
- **THEN** `artifacts.url` es una URL firmada de Storage que descarga el archivo, `url_expires_at` es la fecha de firma más `ARTIFACT_URL_TTL_S`, y el `finish` trae la misma URL

#### Scenario: Archivo fallido
- **WHEN** la generación o la subida fallan
- **THEN** `artifacts.url` y `artifacts.url_expires_at` quedan nulos
