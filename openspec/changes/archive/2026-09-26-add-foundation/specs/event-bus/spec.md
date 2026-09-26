# Spec Delta

## Purpose

Provee un bus de eventos interno donde los endpoints publican los eventos del contrato, desacoplado del transporte, para que la fase 2 lo conecte al WebSocket sin tocar los endpoints.

## ADDED Requirements

### Requirement: Sobre de eventos del contrato
Cada evento publicado SHALL tener el sobre del contrato WebSocket: `type`, `event_id`, `ts` (ISO 8601 en UTC), `agent_id` (uuid o `null`), `task_id` (uuid o `null`) y `data` (objeto). En esta fase `event_id` MUST ser `null` porque los eventos no se persisten.

#### Scenario: Evento publicado
- **WHEN** se publica un evento de tipo `agent.archived` con `data: { "agent_id": "<uuid>" }`
- **THEN** el evento entregado a los suscriptores tiene `type`, `event_id: null`, `ts` en UTC, `agent_id`, `task_id: null` y ese `data`

### Requirement: Suscriptores del bus
El bus SHALL entregar cada evento publicado a todos sus suscriptores, en el orden de publicación. Un suscriptor que falla MUST NOT impedir la entrega a los demás ni hacer fallar la petición que publicó el evento; el fallo MUST quedar en el log.

#### Scenario: Suscriptor que falla
- **WHEN** hay dos suscriptores y el primero lanza una excepción
- **THEN** el segundo recibe el evento, el publicador no recibe error y el log registra el fallo

### Requirement: Registro de eventos en el log
En esta fase el bus SHALL tener un suscriptor que escribe cada evento en el log como un registro JSON con el sobre completo (`type`, `event_id`, `ts`, `agent_id`, `task_id`, `data`). Si `data` contiene un agente, el valor de `instructions` MUST NOT aparecer completo en el log.

#### Scenario: Evento visible en el log
- **WHEN** se publica un evento
- **THEN** el log contiene un registro JSON con su `type` y su `data`

#### Scenario: Instrucciones fuera del log
- **WHEN** se publica un evento cuyo `data.agent.instructions` tiene 5.000 caracteres
- **THEN** el registro del log no contiene ese texto completo
