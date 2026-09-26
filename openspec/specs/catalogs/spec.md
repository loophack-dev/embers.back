# catalogs Specification

## Purpose
Expone qué proveedores, modelos y herramientas se pueden asignar a un agente, a partir de catálogos configurables sin tocar código.

## Requirements

### Requirement: Catálogo de proveedores (GET /providers)
`GET /providers` SHALL responder `{ "items": [ProviderOut] }` con un elemento por proveedor (`anthropic`, `openai`, `gemini`) en el orden del archivo `config/providers.yaml`. Cada elemento MUST tener exactamente `provider`, `available` y `models`; cada modelo, exactamente `id` y `label`. `available` MUST ser `true` solo si la API key del proveedor está configurada y no vacía. El catálogo MUST leerse del archivo de configuración, para cambiar modelos sin tocar código.

#### Scenario: Proveedor sin key
- **WHEN** el servidor no tiene `ANTHROPIC_API_KEY`
- **THEN** el elemento `anthropic` tiene `available: false` y sigue listando sus modelos

#### Scenario: Forma del contrato
- **WHEN** se hace `GET /providers`
- **THEN** cada elemento valida contra `ProviderOut` con el conjunto exacto de llaves

### Requirement: Catálogo de herramientas (GET /tools)
`GET /tools` SHALL responder `{ "items": [ToolOut] }` con exactamente las tres herramientas del demo: `create_document` (`docx`), `create_presentation` (`pptx`) y `create_markdown` (`md`), cada una con `id`, `description` y `artifact_type`. En esta fase las herramientas solo se registran; no se ejecutan.

#### Scenario: Lista de herramientas
- **WHEN** se hace `GET /tools`
- **THEN** `items` contiene las tres herramientas del demo con su `artifact_type`
