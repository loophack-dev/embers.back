# Design

## Context

`add-realtime-gateway` (archivado) dejó `TaskService` con `create_task`/`start`/`accept_answer`/`resume`, la interfaz `AgentRuntime` (`start`, `resume`, `discard` → `Completed | Interrupted`), `FakeRuntime`, `Outbox` como `TaskNotifier`, `TaskSupervisor` y la recuperación al arrancar. Este change agrega el runtime de Strands, la cola, los tiempos y el estado del personaje. Alcance y precisiones: proposal.md.

## Strands Agents: API confirmada

Verificado contra el código instalado de **`strands-agents==1.57.1`** (último en PyPI a 2026-09-26) y con un script sin red que usa un `Model` falso: interrupt condicional, reanudación por id y consumo acumulado.

| Tema | API confirmada |
|---|---|
| Extras | `strands-agents[anthropic,openai,gemini]` → `anthropic 0.125.0`, `openai 2.54.0`, `google-genai 2.25.0` |
| Anthropic | `strands.models.anthropic.AnthropicModel(client_args={"api_key": ...}, model_id=..., max_tokens=..., params={...})`. **`max_tokens` es obligatorio** (`AnthropicConfig`). `params` va directo al request (`temperature`, `top_p`) |
| OpenAI | `strands.models.openai.OpenAIModel(client_args={"api_key": ...}, model_id=..., params={...})`. `params` va directo a Chat Completions (`temperature`, `top_p`, `max_completion_tokens`) |
| Gemini | `strands.models.gemini.GeminiModel(client_args={"api_key": ...}, model_id=..., params={...})`. `params` se expande en `genai.types.GenerateContentConfig` (`temperature`, `top_p`, `max_output_tokens`) |
| Agente | `strands.Agent(model=..., system_prompt=..., tools=[...])`; `await agent.invoke_async(prompt)` devuelve `AgentResult` |
| Herramienta con contexto | `@tool(context=True)` inyecta `tool_context: strands.types.tools.ToolContext` |
| Lanzar interrupt | `tool_context.interrupt(name, reason=...)`: la primera vez lanza `InterruptException`; en la reanudación, la misma llamada **devuelve la respuesta** |
| Detectar | `result.stop_reason == "interrupt"`; `result.interrupts: list[Interrupt]` con `id`, `name`, `reason` |
| Reanudar | Misma instancia: `await agent.invoke_async([{"interruptResponse": {"interruptId": interrupt.id, "response": answer}}])` |
| Consumo | `result.metrics.accumulated_usage["inputTokens" / "outputTokens" / "totalTokens"]`, **acumulado por instancia** (incluye reanudaciones). Por invocación: `result.metrics.agent_invocations[-1].usage` |
| Texto final | `str(result)` |
| Errores del proveedor | `strands.types.exceptions.ModelThrottledException`, `ContextWindowOverflowException`, `MaxTokensReachedException`; los SDK traducen sus errores a estas clases o lanzan sus propios `APIError` |
| Concurrencia | Una instancia no admite dos invocaciones a la vez (`ConcurrencyException`); la cola por agente lo garantiza |

## Goals / Non-Goals

**Goals:** `strands` solo se importa en `runtime/strands_runtime.py`; la cola, los tiempos y la persistencia viven en `domain/tasks.py`, iguales para `strands` y `fake`.

**Non-Goals:** herramientas de archivos, `artifact_error` y Storage (`add-artifact-generation`); cancelación; memoria.

## Decisions

### D1. `StrandsRuntime` (implementa `AgentRuntime`)
- `start(request)`: arma modelo + prompt + herramientas, crea `Agent`, lo guarda en `self._agents[task_id]` junto con el consumo ya reportado, invoca y traduce el resultado.
- `resume(task_id, interrupt_id, answer)`: toma la misma instancia e invoca con `interruptResponse`.
- Traducción: `stop_reason == "interrupt"` → `Interrupted(interrupt.id, reason["question"], reason["options"], usage_delta)`; en otro caso → `Completed(str(result), usage_delta)`. `usage_delta` = acumulado actual − acumulado ya reportado, para que el servicio sume sin duplicar.
- Errores: `ModelThrottledException`, `ContextWindowOverflowException`, `MaxTokensReachedException` y los `APIError` de `anthropic`, `openai` y `google.genai` → `ModelProviderError(tipo)` (excepción propia en `runtime/base.py`); el servicio la convierte en `model_error`.
- `discard(task_id)` borra la instancia.

### D2. `ask_user`
Herramienta creada por tarea (closure con un contador), `@tool(context=True)`, entrada `question: str`, `options: list[str] | None`. Si el contador < `MAX_QUESTIONS_PER_TASK`: incrementa y llama `tool_context.interrupt("ask_user", reason={"question", "options"})`; lo que devuelve (la respuesta en la reanudación) es el resultado de la herramienta. Si ya llegó al límite: devuelve "Question limit reached. Continue with reasonable assumptions and mention them in your summary." sin interrumpir. Las opciones se recortan a 6 y la pregunta a 1.000 caracteres para cumplir el contrato.

### D3. Modelo por proveedor
Función `build_model(snapshot, settings)` con un `match` sobre `provider`: construye `AnthropicModel`, `OpenAIModel` o `GeminiModel` con `client_args={"api_key": ...}` y traduce `params` no nulos a los nombres de cada SDK (proposal, precisiones 1 y 2).

### D4. System prompt
`build_system_prompt(snapshot, expected_output)` en `domain/prompt.py` (sin Strands): une los bloques no vacíos con líneas en blanco. Bloque 1 con las etiquetas `Name`, `Role`, `Personality`, `Tone` (omite las nulas).

### D5. Cola y tiempos en `TaskService`
- `AgentLane` por agente: `current: UUID | None`, `queue: deque[UUID]`. `create_task` decide `working`/`queued` con el lane (y crea la fila con ese estado); `start` solo arranca si la tarea es la `current`. Al terminar la actual, el lane toma la siguiente y la inicia.
- Cada tramo (`runtime.start` o `runtime.resume`) corre con `asyncio.timeout(remaining)`; `remaining` = `TASK_TIMEOUT_S` − tiempo ya trabajado (guardado en memoria por tarea). `TimeoutError` → `finish` `timeout` + `discard`.
- Vencimiento de preguntas: al enviar `ask` se programa `asyncio` con `ASK_TIMEOUT_S`; si la pregunta sigue `pending`, se marca `expired` y la tarea termina con `timeout`. Se cancela al llegar el `answer`. La expiración y el `answer` se serializan con el `for update` existente: el `answer` que llega tarde recibe `question_not_pending`.

### D6. Estado del personaje
`AgentRepository.open_tasks(agent_ids)` devuelve, por agente, la tarea en `working`/`waiting_user` y las `queued` ordenadas por `created_at`, en una sola consulta. `to_agent_out` recibe ese resumen; `GET /agents` lo pide para todos los agentes listados (sin N+1). Los eventos `agent.*` no cambian.

## Risks / Trade-offs

- [Nombres de parámetros de OpenAI/Gemini] Verificados en el código de Strands, no contra la API real (no hay keys) → se confirman en la primera prueba real; son un `dict` fácil de ajustar.
- [Consumo acumulado por instancia] Si Strands cambia la semántica, el delta falla → el cálculo está en un solo lugar.
- [Cola y timers en memoria] Un reinicio los pierde → recuperación existente marca `failed`.
- [Sin tests] La lógica de cola y tiempos solo se verifica a mano, con `AGENT_RUNTIME=fake` y tiempos cortos (`TASK_TIMEOUT_S`, `ASK_TIMEOUT_S` y `FAKE_RUNTIME_DELAY_S` pequeños).

## Migration Plan

Sin migraciones nuevas. Instalar la dependencia con `uv sync`. Rollback: `AGENT_RUNTIME=fake`.
