# Tasks

## 1. Base de datos

- [x] 1.1 Crear las migraciones de `tasks`, `task_questions` y `task_events` (regla de nulos, checks, índice único parcial de pregunta pendiente, índices); verificar con `npx supabase db reset` y un `insert` manual de dos preguntas `pending` para la misma tarea que la base rechaza
- [x] 1.2 Implementar `db/tasks_repository.py` y `db/task_events_repository.py` (SQL parametrizado, `for update` en `answer`, recuperación al arrancar, lectura de `ask` pendientes); verificar con `ruff` y `mypy`

## 2. Contratos y runtime

- [x] 2.1 Implementar `contracts/ws.py` (sobres, `DelegateData`, `AnswerData`, `AckData`, `AskData`, `FinishData`, `TaskError`, `TaskUsage`, `ArtifactOut`) y `AgentSnapshot`; verificar con `mypy`
- [x] 2.2 Implementar `runtime/base.py` (`AgentRuntime`, `RunRequest`, `Completed`, `Interrupted`, `Usage`) y `runtime/fake.py`; agregar `AGENT_RUNTIME` y `FAKE_RUNTIME_DELAY_S` a `Settings` y `.env.example`; verificar que un valor inválido impide el arranque

## 3. Tareas y gateway

- [x] 3.1 Implementar `domain/tasks.py` (`TaskService`: delegate, answer, ejecución en segundo plano con `TaskSupervisor`, ask, finish, acumulado de `usage`) y los puertos `TaskRepository` y `TaskNotifier`
- [x] 3.2 Implementar `realtime/` (`ConnectionRegistry`, `Outbox`) y `api/routes/ws.py` (parseo en dos pasos, errores, reenvío de `ask` pendientes); montar la ruta y la recuperación al arrancar en `main.py`
- [x] 3.3 Agregar `TaskEventsSubscriber` al bus; verificar con un `POST /agents` que aparece `agent.created` en `task_events` con `direction` nulo

## 4. Verificación y documentación

- [x] 4.1 Recorrer con un cliente WebSocket (script ad hoc en el scratchpad, no suite de tests) los escenarios de las specs: `ack`, cada `error`, `unknown_command`, difusión a dos conexiones, `ask`/`answer`/`finish`, reenvío al reconectar, `question_not_pending` y las filas de `task_events`
- [x] 4.2 Documentar en `README.md` el WebSocket con ejemplos de `delegate`, `ask`, `answer` y `finish`; verificar `ruff check`, `ruff format --check` y `mypy src`
