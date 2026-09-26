# Spec Delta

## Purpose

Persiste las tareas delegadas a los agentes y las preguntas que el agente le hace a la persona, con su ciclo de vida.

## ADDED Requirements

### Requirement: Tablas de tareas y preguntas
Las migraciones SHALL crear `tasks` y `task_questions` según la sección 3 del documento de fase 2, con la regla de nulos: en `tasks` no aceptan nulo `id`, `workspace_id`, `agent_id`, `instruction` (1–4000), `status`, `agent_snapshot` y `created_at`; en `task_questions`, `id`, `workspace_id`, `task_id`, `question` (1–1000), `status` y `asked_at`. `tasks.status` MUST ser `queued`, `working`, `waiting_user`, `completed`, `failed` o `canceled`; `task_questions.status`, `pending`, `answered` o `expired`; `options`, si existe, una lista de hasta 6 textos. MUST existir como máximo una pregunta `pending` por tarea.

#### Scenario: Segunda pregunta pendiente
- **WHEN** se inserta una segunda pregunta `pending` para la misma tarea
- **THEN** Postgres la rechaza por el índice único parcial

### Requirement: Ciclo de vida de la tarea
Al crearse, la tarea SHALL guardar `agent_snapshot` (nombre, versión, `model_config`, `identity`, `instructions`, `tools` del agente en ese momento). Al empezar MUST pasar a `working` y fijar `started_at` la primera vez. Al preguntar MUST pasar a `waiting_user`; con la respuesta, de nuevo a `working`. Al terminar MUST quedar `completed` o `failed` con `result_text`, `error`, `usage` y `finished_at`.

#### Scenario: Tarea completada
- **WHEN** una tarea termina bien
- **THEN** la fila queda `completed`, con `result_text`, `usage`, `started_at` y `finished_at`, y `error` nulo

#### Scenario: Snapshot inmutable
- **WHEN** el agente se edita después de crear la tarea
- **THEN** `agent_snapshot` de la tarea no cambia

### Requirement: Recuperación al arrancar
Al arrancar el backend, las tareas en `queued`, `working` o `waiting_user` SHALL pasar a `failed` con `error: { code: "internal_error", ... }` y `finished_at`, y sus preguntas `pending` MUST pasar a `expired`.

#### Scenario: Reinicio con tarea abierta
- **WHEN** el backend se reinicia con una tarea en `waiting_user`
- **THEN** la tarea queda `failed` con `internal_error` y su pregunta queda `expired`
