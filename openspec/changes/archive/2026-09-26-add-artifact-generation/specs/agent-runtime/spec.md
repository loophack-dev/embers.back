# Spec Delta

## MODIFIED Requirements

### Requirement: Herramientas del agente
El agente SHALL tener siempre `ask_user` (`question` y `options` opcional, hasta 6) y las herramientas de archivos (`create_document`, `create_presentation`, `create_markdown`) que estén en su `tools`. Un id de `tools` sin implementación MUST omitirse con un aviso en el log.

#### Scenario: Solo ask_user disponible
- **WHEN** el agente tiene `tools: []`
- **THEN** el agente se construye solo con `ask_user`

#### Scenario: Herramientas de archivos
- **WHEN** el agente tiene `tools: ["create_document", "create_markdown"]`
- **THEN** el agente se construye con `ask_user`, `create_document` y `create_markdown`

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
