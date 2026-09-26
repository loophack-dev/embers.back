# Proposal

## Why

El gateway (`add-realtime-gateway`) ya recibe `delegate` y `answer` y entrega `ack`, `ask` y `finish`, pero con un runtime falso. Falta que el agente trabaje de verdad: ejecutar la tarea con Strands Agents contra el proveedor del agente, preguntar a la persona con interrupts, respetar una tarea a la vez por agente y los límites de tiempo, y reflejar el estado real del personaje en `AgentOut`.

## What Changes

- **Cola en memoria por agente**, una tarea a la vez, en orden de llegada. El `ack` de `delegate` dice `working` si el agente está libre y `queued` si está ocupado. Una tarea en `waiting_user` ocupa al agente. Distintos agentes trabajan en paralelo.
- **Runtime de Strands** (`AGENT_RUNTIME=strands`, nuevo valor por defecto), detrás de la interfaz `AgentRuntime` que ya existe: agente nuevo por tarea desde `agent_snapshot`, proveedor directo, parámetros no nulos, system prompt en cuatro bloques y herramientas según `tools` más `ask_user`.
- **`ask_user` con interrupts**: guarda la pregunta con su `interrupt_id`, la tarea pasa a `waiting_user` y sale `ask`; con el `answer`, se reanuda la misma instancia. Máximo 3 preguntas por tarea (`MAX_QUESTIONS_PER_TASK`); desde la cuarta, la herramienta le dice al modelo que siga con supuestos razonables.
- **Tiempos y errores**: trabajo > `TASK_TIMEOUT_S` (600 s, sin contar esperas) → `timeout`; pregunta sin respuesta en `ASK_TIMEOUT_S` (1.800 s) → pregunta `expired` y `timeout`; error del proveedor → `model_error` sin datos sensibles; error no previsto → `internal_error`. Todos terminan en `finish` fallido y el agente pasa a la siguiente tarea.
- **Resultado**: `result_text` = último mensaje del agente; `usage` acumulado de toda la tarea (incluidas reanudaciones) con `model_id`; `started_at` y `finished_at`.
- **`AgentOut` real**: `character_status` (`working`, `waiting` o `idle`), `current_task_id` y `queued_task_ids` según las tareas del agente. El enum `CharacterStatus` pasa a `idle | working | waiting` (contrato actualizado en `add-realtime-gateway`).
- `provider_unavailable` se valida con `AGENT_RUNTIME=strands`.
- Dependencia nueva: `strands-agents[anthropic,openai,gemini]==1.57.1`. Sin Bedrock, AWS ni LiteLLM.
- La recuperación al arrancar (tareas abiertas → `failed` con `internal_error`) ya quedó en `add-realtime-gateway`; aquí no cambia.

### Precisiones que los documentos no definen (a aprobar)

1. **`max_tokens` de Anthropic**: Strands lo exige en `AnthropicModel`. Si `params.max_tokens` es nulo se usa **8192**. En OpenAI y Gemini, si es nulo no se envía.
2. **Nombres de parámetros por proveedor**: OpenAI recibe `max_completion_tokens` (el parámetro vigente de Chat Completions; los modelos de razonamiento rechazan `max_tokens`; se confirma con la primera llamada real); Gemini recibe `max_output_tokens`; `temperature` y `top_p` igual en los tres.
3. **Herramientas de archivos**: llegan en `add-artifact-generation`. En este change el agente solo tiene `ask_user`; los ids de `tools` sin implementación se omiten con un aviso en el log. El bloque 4 del prompt (formato esperado) sí se arma ya.
4. **Idioma del system prompt**: los bloques fijos (reglas de trabajo y formato esperado) se escriben en inglés; la regla "responde en el idioma de la instrucción" hace que el agente conteste en español si la instrucción lo está.
5. **Mensaje de `model_error`**: "The model provider returned an error (<tipo>)." — solo el tipo de excepción, nunca el cuerpo de la respuesta ni la key.
6. **Tiempo de trabajo**: se mide por tramos de ejecución del agente (inicio y cada reanudación) y se descuenta del presupuesto de 600 s; la espera en `waiting_user` no cuenta.
7. **Orden de la cola**: si el backend se reinicia, la cola se pierde junto con las tareas (quedan `failed` por la recuperación existente).
8. **Prueba real con los tres proveedores (CA12)**: sin tests automatizados; se verifica a mano con los proveedores que tengan API key en `.env`. Hoy el `.env` local no tiene ninguna, así que CA12 queda pendiente de tus keys.

## Capabilities

### New Capabilities
- Ninguna.

### Modified Capabilities
- `agent-runtime`: selección `strands | fake` (por defecto `strands`) y runtime de Strands con proveedores directos, prompt, herramientas e interrupts.
- `tasks`: cola por agente, preguntas con límite y vencimiento, tiempos, errores y resultado.
- `realtime-gateway`: el `ack` de `delegate` puede ser `queued`.
- `agents`: `AgentOut` con `character_status`, `current_task_id` y `queued_task_ids` reales.

## Impact

- `src/embers/runtime/strands_runtime.py` (único módulo que importa `strands`), `domain/tasks.py` (cola, tiempos), `domain/agents.py` y `db/agents_repository.py` (estado del personaje), `config.py`.
- Variables nuevas: `TASK_TIMEOUT_S`, `ASK_TIMEOUT_S`, `MAX_QUESTIONS_PER_TASK`; `AGENT_RUNTIME` acepta `strands`.
- Sin tests automatizados (decisión del usuario).
