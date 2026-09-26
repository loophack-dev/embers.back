# Spec Delta

## MODIFIED Requirements

### Requirement: Sobre de eventos del contrato
Cada evento publicado SHALL tener el sobre: `type`, `event_id`, `ts` (ISO 8601 en UTC), `agent_id` (uuid o `null`), `task_id` (uuid o `null`) y `data` (objeto). En el evento que reciben los suscriptores `event_id` MUST ser `null`; la persistencia en `task_events` asigna el id de la fila.

#### Scenario: Evento publicado
- **WHEN** se publica un evento de tipo `agent.archived` con `data: { "agent_id": "<uuid>" }`
- **THEN** el evento entregado a los suscriptores tiene `type`, `event_id: null`, `ts` en UTC, `agent_id`, `task_id: null` y ese `data`

## ADDED Requirements

### Requirement: Persistencia de eventos internos
El bus SHALL tener un suscriptor que guarda cada evento interno (`agent.created`, `agent.updated`, `agent.archived`) en `task_events` con su `type`, `agent_id`, `task_id`, `data` y `direction` nulo. Estos eventos MUST NOT enviarse por `/ws`.

#### Scenario: Evento interno guardado
- **WHEN** se crea un agente por REST
- **THEN** `task_events` tiene una fila `agent.created` con `direction` nulo y el `AgentOut` en `data`, y ninguna conexión WebSocket recibe mensaje
