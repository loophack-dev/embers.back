# agent-runtime Specification

## Purpose
Define el runtime que ejecuta una tarea con un agente, intercambiable por configuración, e incluye un runtime falso para integrar el front sin llamar a ningún modelo.

## Requirements

### Requirement: Selección del runtime
El runtime SHALL elegirse con `AGENT_RUNTIME`: `strands` (valor por defecto) o `fake`. Un valor no soportado MUST impedir el arranque con un error de configuración. Ningún módulo fuera del runtime de Strands MUST importar `strands`.

#### Scenario: Runtime no soportado
- **WHEN** la app arranca con `AGENT_RUNTIME=otro`
- **THEN** el arranque falla indicando el valor inválido

#### Scenario: Runtime por defecto
- **WHEN** la app arranca sin `AGENT_RUNTIME`
- **THEN** usa el runtime de Strands

### Requirement: Runtime falso
Con `AGENT_RUNTIME=fake`, cada tarea SHALL esperar `FAKE_RUNTIME_DELAY_S` segundos (por defecto 3) y terminar con un `finish` `completed`, `result_text` fijo, `error: null` y `usage` en ceros con el `model_id` del agente. Si la instrucción contiene "pregunta" (sin distinguir mayúsculas), MUST enviar primero un `ask` y terminar solo después del `answer`, incluyendo la respuesta en `result_text`. Si la tarea trae `expected_output`, MUST generar un archivo mínimo de ese tipo con las mismas herramientas de archivos; si no, `artifacts` MUST ser `[]`. No MUST llamar a ningún proveedor.

#### Scenario: CA14 · Flujo sin modelo
- **WHEN** con `AGENT_RUNTIME=fake` se envía `delegate` con "Resume el trimestre"
- **THEN** se recibe `ack` con `status: working` y, unos segundos después, `finish` `completed` con el texto fijo

#### Scenario: Flujo con pregunta
- **WHEN** se envía `delegate` con "Tengo una pregunta sobre el informe"
- **THEN** llega un `ask` con `options`, la tarea queda en `waiting_user`, y tras el `answer` "Formal" llega un `finish` `completed` cuyo `result_text` contiene "Formal"

#### Scenario: Runtime falso con archivo
- **WHEN** con `AGENT_RUNTIME=fake` se envía `delegate` con `expected_output: "pptx"`
- **THEN** el `finish` `completed` trae un artefacto `pptx` `ready`

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
El agente SHALL tener siempre `ask_user` (`question` y `options` opcional, hasta 6) y las herramientas de archivos (`create_document`, `create_presentation`, `create_markdown`) que estén en su `tools`. Un id de `tools` sin implementación MUST omitirse con un aviso en el log.

#### Scenario: Solo ask_user disponible
- **WHEN** el agente tiene `tools: []`
- **THEN** el agente se construye solo con `ask_user`

#### Scenario: Herramientas de archivos
- **WHEN** el agente tiene `tools: ["create_document", "create_markdown"]`
- **THEN** el agente se construye con `ask_user`, `create_document` y `create_markdown`
