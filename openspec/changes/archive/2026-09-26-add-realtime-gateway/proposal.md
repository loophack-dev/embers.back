# Proposal

## Why

La fase 2 lleva la conversación con el agente al WebSocket: la persona delega una tarea, el agente puede preguntar y entrega un resultado. Antes de conectar Strands, el front necesita un `/ws` estable con el protocolo oficial (`delegate`, `answer`, `ack`, `error`, `ask`, `finish`) y un runtime falso para integrarse sin llamar a ningún modelo.

## What Changes

- Endpoint `GET /ws` (WebSocket) con el sobre del contrato (§5 de `embers-modelos-y-contratos.md`) en ambas direcciones.
- Registro de conexiones: `ack` y `error` solo a quien envió el mensaje; `ask` y `finish` a todas las conexiones abiertas.
- Validación de `delegate` y `answer` con los errores del documento de fase (§4) y del contrato: `unknown_command`, `validation_error`, `not_found`, `agent_archived`, `provider_unavailable`, `question_not_pending`.
- Reenvío de los `ask` pendientes al abrir una conexión.
- Migraciones de **`tasks`**, **`task_questions`** y **`task_events`** con la regla de nulos de la fase 2, checks de estado e índice único parcial de pregunta pendiente. `tasks` y `task_questions` se adelantan desde `add-agent-execution` (decisión del usuario), porque `ack`, `answer`, el reenvío de `ask` y la FK de `task_events` las necesitan.
- Registro de cada mensaje entrante y saliente en `task_events` con `direction`. El bus de eventos de la fase 1 suma un suscriptor que guarda `agent.created`, `agent.updated` y `agent.archived` con `direction` nulo.
- Interfaz propia del runtime de agentes (`AgentRuntime`) y un **runtime falso** (`AGENT_RUNTIME=fake`): espera unos segundos y termina con un texto fijo; si la instrucción contiene "pregunta", primero pregunta.
- Orquestación mínima de la tarea: crear con `agent_snapshot`, `ack`, ejecutar en segundo plano, `ask` → `waiting_user`, `answer` → reanudar, `finish`. La cola por agente, Strands, tiempos y estado del personaje llegan en `add-agent-execution`.
- Al arrancar, las tareas abiertas pasan a `failed` con `internal_error` (las instancias en memoria se pierden).
- **Contrato actualizado** (`docs/embers-modelos-y-contratos.md`): la sección 5 tenía el protocolo anterior (`hello`, `task.create`, …). Se reescribió según el documento de fase 2: sobre, seis mensajes, `DelegateData`, `AnswerData`, `AckData`, `AskData`, `FinishData`, `ArtifactOut`, validaciones; `CharacterStatus` = `idle|working|waiting`; `TaskStatus` suma `waiting_user`; errores `question_not_pending` y `artifact_error`; tabla `task_questions`; `task_events.direction`; puerto 3523. Copia del original en el scratchpad de la sesión.

### Precisiones que los documentos no definen (a aprobar)

1. **`event_id`** es el `id` de la fila en `task_events`; `ts` es su `created_at`. `task_events.data` guarda el mensaje sin esos dos campos.
2. **Reenvío de `ask`**: se reenvía el mismo mensaje original (mismo `event_id`), sin crear una fila nueva, para que el front pueda deduplicar por `event_id`.
3. **Mensajes ilegibles**: JSON inválido se guarda con `type: "unknown"` y `data: { "raw": <primeros 2.000 caracteres> }`; el `error` sale con `request_id: null` si no se pudo leer.
4. **Runtime falso sin API key**: con `AGENT_RUNTIME=fake` no se valida `provider_unavailable`, para que el front se integre sin keys. Con `strands` sí.
5. **Runtime por defecto** en este change: `fake` (es el único). `add-agent-execution` cambia el valor por defecto a `strands`.
6. **Runtime falso**: espera `FAKE_RUNTIME_DELAY_S` (por defecto 3 s). Si la instrucción contiene "pregunta" (sin distinguir mayúsculas), pregunta "¿Qué detalle quieres que tenga en cuenta?" con opciones `["Formal", "Informal"]`; al reanudar, termina con "Tarea completada por el runtime falso. Respuesta recibida: {answer}". Sin pregunta: "Tarea completada por el runtime falso.". `usage` en ceros con el `model_id` del snapshot.
7. **Sin cola en este change**: cada `delegate` válido responde `ack` con `status: working` y se ejecuta de inmediato; la cola por agente (y `queued`) llega en `add-agent-execution`.
8. **Logs**: cada mensaje se registra con su tipo, dirección e ids; `instruction`, `answer` y `result_text` se truncan a 80 caracteres.

## Capabilities

### New Capabilities
- `realtime-gateway`: endpoint `/ws`, sobre, entrega, validación, reenvío de `ask` y registro en `task_events`.
- `tasks`: persistencia de tareas y preguntas, ciclo de vida básico y recuperación al arrancar.
- `agent-runtime`: interfaz del runtime y runtime falso.

### Modified Capabilities
- `event-bus`: los eventos internos también se guardan en `task_events`.

## Impact

- Nuevas migraciones, módulos en `src/embers/{contracts,domain,db,events,api}` y un paquete `src/embers/runtime/`.
- Nuevas variables: `AGENT_RUNTIME`, `FAKE_RUNTIME_DELAY_S`.
- Sin dependencias nuevas (FastAPI ya incluye WebSocket; `websockets` viene con `uvicorn[standard]`).
- Sin tests automatizados (decisión del usuario); verificación manual con un cliente WebSocket.
