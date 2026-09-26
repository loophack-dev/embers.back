# Design

## Context

Fase 1 archivada (`openspec/specs/`): `create_app` con `app.state`, `Database` (asyncpg, codec jsonb), `ApiError`, `EventBus` + `LogSubscriber`, `AgentService` y `PgAgentRepository`. Protocolo en la §5 del contrato (reescrita en este change) y reglas en la §4 del documento de fase 2. Ver proposal.md para el alcance y las precisiones aprobables.

## Goals / Non-Goals

**Goals:**
- El gateway solo sabe de sobres, conexiones y validación; la lógica de tareas vive en `domain/tasks.py`; el runtime está detrás de un `Protocol`.
- Toda interfaz que `add-agent-execution` necesite (runtime, notificador, repositorio de tareas) nace aquí con su forma final.

**Non-Goals:**
- Cola por agente, `queued`, tiempos (`TASK_TIMEOUT_S`, `ASK_TIMEOUT_S`), límite de preguntas, Strands, `character_status` real, artefactos.

## Decisions

### D1. Capas

```
api/routes/ws.py ─────────► realtime/ (ConnectionRegistry, Outbox) ──► db/task_events_repository.py
      │ parse + valida sobre            ▲ implementa TaskNotifier
      ▼                                 │
domain/tasks.py (TaskService) ──► domain/ports.py: TaskRepository, TaskNotifier
      │                                   AgentRepository (fase 1)
      ▼
runtime/base.py: AgentRuntime (Protocol) ◄── runtime/fake.py   (runtime/strands.py en add-agent-execution)
```
- `TaskService.delegate()` y `.answer()` validan, persisten y devuelven el `AckData`; la ruta envía el `ack`. La ejecución corre en segundo plano (`TaskSupervisor`: `asyncio.create_task` + set de tareas vivas, cancelado en el apagado).
- `TaskNotifier` (puerto del dominio) tiene `ask(task, question)` y `finish(task, ...)`; `Outbox` lo implementa guardando en `task_events` y difundiendo.
- Ninguna parte fuera de `runtime/` conoce la implementación del runtime; `main.py` lo elige con `AGENT_RUNTIME`.

### D2. Interfaz del runtime (forma final)

```python
@dataclass(frozen=True)
class RunRequest: task_id; snapshot: AgentSnapshot; instruction: str; expected_output: str | None

@dataclass(frozen=True)
class Usage: input_tokens: int; output_tokens: int; total_tokens: int

@dataclass(frozen=True)
class Completed: text: str | None; usage: Usage

@dataclass(frozen=True)
class Interrupted: interrupt_id: str; question: str; options: list[str] | None; usage: Usage

RunOutcome = Completed | Interrupted

class AgentRuntime(Protocol):
    async def start(self, request: RunRequest) -> RunOutcome
    async def resume(self, task_id: UUID, interrupt_id: str, answer: str) -> RunOutcome
    def discard(self, task_id: UUID) -> None   # libera la instancia en memoria
```
Encaja 1:1 con los interrupts de Strands (el agente se detiene con `stop_reason="interrupt"` y se reanuda con la respuesta ligada al id). Los fallos se lanzan como excepciones; en este change todas terminan en `internal_error` (el mapeo a `model_error`/`timeout` llega con Strands). `usage` es el consumo de cada paso; el servicio lo acumula.

### D3. Contratos WebSocket
`contracts/ws.py`: `ClientMessage` (`type: Literal["delegate","answer"]`, `request_id` 1–64, `data: dict`), `DelegateData`, `AnswerData` (con `extra="forbid"`), `ServerMessage[T]`, `AckData`, `AskData`, `FinishData`, `TaskError`, `TaskUsage`, `ArtifactOut`. Parseo en dos pasos: primero JSON y `type` (→ `unknown_command`), después sobre y `data` (→ `validation_error` con la misma forma `details.fields` de REST; los campos de `data` se reportan sin prefijo, p. ej. `instruction`).

### D4. Persistencia
Migraciones `tasks`, `task_questions`, `task_events` (FK con `on delete cascade`, `workspace_id` con default de la oficina, checks de estado y de `options` como arreglo de ≤ 6, índice único parcial `task_questions (task_id) where status = 'pending'`, índices de la fase). `PgTaskRepository` con SQL parametrizado. `answer` valida y marca la pregunta dentro de una transacción con `select ... for update` sobre la pregunta para que dos `answer` simultáneos no pasen ambos.

### D5. Entrega y registro
- `ConnectionRegistry`: conexiones con un `asyncio.Lock` por conexión para serializar envíos; una conexión que falla al enviar se retira.
- `Outbox.send_to(conn, ...)` (ack/error) y `Outbox.broadcast(...)` (ask/finish): primero insertan en `task_events` (`returning id, created_at`), después arman el sobre con `event_id`/`ts` y envían.
- Entrantes: se guardan antes de validar (`direction='in'`); ilegibles con `type='unknown'`.
- Al conectar: se registra la conexión y se le reenvían los `ask` pendientes leyendo la fila original del `ask` en `task_events` (mismo `event_id`). Si llega un `ask` nuevo entre el registro y el reenvío podría duplicarse; el front deduplica por `event_id`.

### D6. Eventos internos
`TaskEventsSubscriber` en el bus de la fase 1 guarda `agent.*` con `direction` nulo. Los endpoints REST no cambian.

### D7. Recuperación
En el lifespan, después de abrir la base: `update tasks set status='failed', error=..., finished_at=now() where status in (...)` y preguntas `pending` → `expired`. Si la base no responde, se registra y la app arranca igual.

## Risks / Trade-offs

- [Sin cola en este change] Dos `delegate` al mismo agente corren en paralelo con el runtime falso → aceptable hasta `add-agent-execution`, que agrega la cola sin cambiar el gateway.
- [Instancias en memoria] Un reinicio pierde las tareas abiertas → recuperación explícita a `failed`.
- [`finish` perdido sin conexiones] Por diseño de la fase; el front consulta por REST.

## Migration Plan

`npx supabase db reset` en local; `npx supabase db push` en remoto. Rollback: `drop table task_events, task_questions, tasks`.
