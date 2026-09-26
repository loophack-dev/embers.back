# Spec Delta

## MODIFIED Requirements

### Requirement: Selección del runtime
El runtime SHALL elegirse con `AGENT_RUNTIME`: `strands` (valor por defecto) o `fake`. Un valor no soportado MUST impedir el arranque con un error de configuración. Ningún módulo fuera del runtime de Strands MUST importar `strands`.

#### Scenario: Runtime no soportado
- **WHEN** la app arranca con `AGENT_RUNTIME=otro`
- **THEN** el arranque falla indicando el valor inválido

#### Scenario: Runtime por defecto
- **WHEN** la app arranca sin `AGENT_RUNTIME`
- **THEN** usa el runtime de Strands

## ADDED Requirements

### Requirement: Agente de Strands por tarea
Con `AGENT_RUNTIME=strands`, cada tarea SHALL ejecutarse con un agente de Strands nuevo construido desde `tasks.agent_snapshot`, conectado directo al proveedor (`anthropic`, `openai` o `gemini`) con la API key del servidor. Los parámetros de `model_config.params` MUST pasarse solo si no son nulos; si `max_tokens` es nulo y el proveedor lo exige (Anthropic), MUST usarse 8192. MUST NOT usarse Bedrock, AWS ni LiteLLM.

#### Scenario: CA1 · Tarea completada con el proveedor
- **WHEN** se delega "Resume en tres puntos las ventajas del trabajo remoto" a un agente libre con API key de su proveedor
- **THEN** se recibe `ack` con `status: working` y después todas las conexiones reciben `finish` con `status: completed`, `result_text` no vacío y `usage` con tokens mayores que cero y el `model_id` del agente

#### Scenario: CA12 · Los tres proveedores
- **WHEN** se ejecuta la misma tarea con un agente de cada proveedor que tenga API key
- **THEN** los tres terminan con `finish` `completed`

### Requirement: System prompt en cuatro bloques
El system prompt SHALL tener, en este orden: (1) identidad con nombre, rol, personalidad y tono no nulos; (2) `instructions` del agente si no está vacío; (3) reglas de trabajo de Embers (responder en el idioma de la instrucción, usar `ask_user` solo si falta información indispensable y una sola vez, usar la herramienta de archivos si se pide un documento, terminar con un resumen breve); (4) si hay `expected_output`, la indicación de entregar un archivo de ese tipo. El prompt completo MUST NOT escribirse en el log.

#### Scenario: Agente sin instrucciones
- **WHEN** el agente tiene `instructions` vacío
- **THEN** el system prompt tiene los bloques 1 y 3 (y el 4 si hay `expected_output`), sin un bloque vacío

### Requirement: Herramientas del agente
El agente SHALL tener siempre `ask_user` (`question` y `options` opcional, hasta 6) y las herramientas de `tools` que tengan implementación. Los ids sin implementación MUST omitirse con un aviso en el log.

#### Scenario: Solo ask_user disponible
- **WHEN** el agente tiene `tools: ["create_document"]` y esa herramienta aún no está implementada
- **THEN** el agente se construye con `ask_user` y el log avisa que `create_document` se omitió
