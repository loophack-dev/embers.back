# Spec Delta

## Purpose

Define el runtime que ejecuta una tarea con un agente, intercambiable por configuración, e incluye un runtime falso para integrar el front sin llamar a ningún modelo.

## ADDED Requirements

### Requirement: Selección del runtime
El runtime SHALL elegirse con `AGENT_RUNTIME`. En este change el único valor válido es `fake` (valor por defecto); un valor no soportado MUST impedir el arranque con un error de configuración.

#### Scenario: Runtime no soportado
- **WHEN** la app arranca con `AGENT_RUNTIME=otro`
- **THEN** el arranque falla indicando el valor inválido

### Requirement: Runtime falso
Con `AGENT_RUNTIME=fake`, cada tarea SHALL esperar `FAKE_RUNTIME_DELAY_S` segundos (por defecto 3) y terminar con un `finish` `completed`, `result_text` fijo, `artifacts: []`, `error: null` y `usage` en ceros con el `model_id` del agente. Si la instrucción contiene "pregunta" (sin distinguir mayúsculas), MUST enviar primero un `ask` y terminar solo después del `answer`, incluyendo la respuesta en `result_text`. No MUST llamar a ningún proveedor.

#### Scenario: CA14 · Flujo sin modelo
- **WHEN** con `AGENT_RUNTIME=fake` se envía `delegate` con "Resume el trimestre"
- **THEN** se recibe `ack` con `status: working` y, unos segundos después, `finish` `completed` con el texto fijo

#### Scenario: Flujo con pregunta
- **WHEN** se envía `delegate` con "Tengo una pregunta sobre el informe"
- **THEN** llega un `ask` con `options`, la tarea queda en `waiting_user`, y tras el `answer` "Formal" llega un `finish` `completed` cuyo `result_text` contiene "Formal"
