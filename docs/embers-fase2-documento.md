# Embers · Fase 2: el agente trabaja

**Objetivo:** la persona le delega una tarea a un agente desde el front. El agente la resuelve con Strands Agents, puede hacer preguntas si le falta información, y entrega su respuesta junto con los archivos generados (docx, pptx o md). Toda la conversación ocurre por WebSocket con cuatro mensajes: `delegate`, `ask`, `answer` y `finish`.

**Documento de referencia:** `embers-modelos-y-contratos.md`. El protocolo WebSocket oficial está en su sección 5; si algo de esta fase lo contradice, manda el documento oficial.

**Requisito previo:** la fase 1 está terminada. Los agentes se crean y configuran por REST.

---

## 1. Alcance

### Incluido

| # | Capacidad | Resultado visible |
|---|---|---|
| 1 | Gateway WebSocket | El front se conecta a `/ws`, envía `delegate` y `answer`, y recibe `ack`, `error`, `ask` y `finish` |
| 2 | Tareas | Cada `delegate` crea una tarea persistida, con cola por agente |
| 3 | Ejecución con Strands | El agente resuelve la tarea con su proveedor, identidad y system prompt, conectándose directo al proveedor |
| 4 | Preguntas a la persona | El agente pregunta cuando le falta información; la tarea se pausa hasta el `answer` |
| 5 | Archivos | El agente genera docx, pptx o md; se suben a Supabase Storage y viajan en el `finish` |
| 6 | Descarga | `GET /artifacts/{id}/download` renueva la URL firmada |
| 7 | Estado del personaje real | `AgentOut` ya refleja `character_status`, `current_task_id` y `queued_task_ids` |

### Fuera de esta fase

| Tema | Cuándo |
|---|---|
| Memoria, feedback y endpoints de memoria | Fase de memoria |
| Cancelar tareas | Más adelante; `canceled` queda reservado |
| Eventos de progreso o streaming de texto | No se usan: el protocolo tiene solo los mensajes definidos |
| Delegación entre agentes, varias oficinas, autenticación | Después del hackatón |
| Otros formatos (xlsx, imágenes, PDF) | Después del hackatón |

---

## 2. Flujo general

| # | Dónde | Qué pasa |
|---|---|---|
| 1 | Front | Envía `delegate` con el agente y la instrucción |
| 2 | Back | Valida el mensaje. Si hay error, responde `error` y no crea nada |
| 3 | Back | Crea la tarea con una copia de la configuración del agente y responde `ack`: `working` si el agente está libre, `queued` si está ocupado |
| 4 | Back | Cuando el agente está libre, arma el agente de Strands y lo ejecuta |
| 5 | Agente | Si le falta información, usa la herramienta `ask_user`. El back guarda la pregunta, envía `ask` y la tarea pasa a `waiting_user` |
| 6 | Front | Envía `answer`. El back responde `ack` y reanuda al agente con la respuesta |
| 7 | Agente | Usa las herramientas de archivos. Cada archivo se genera, se sube a Storage y queda listo |
| 8 | Back | Al terminar el agente, guarda el resultado y envía `finish` con el texto, los archivos y el consumo |
| 9 | Back | Si el agente tiene otra tarea en cola, la inicia |

---

## 3. Modelo de datos de la fase

Esta fase crea `tasks`, `task_questions`, `artifacts` y `task_events`, y el bucket `artifacts` de Storage. Se aplica la misma regla de nulos de la fase 1: **los campos mínimos no aceptan nulo, el resto sí**.

### tasks

| Columna | Tipo | Nulo | Por defecto | Notas |
|---|---|---|---|---|
| `id` | uuid | no | `gen_random_uuid()` | PK |
| `workspace_id` | uuid | no | oficina por defecto | FK → workspaces |
| `agent_id` | uuid | no | | FK → agents |
| `instruction` | text | no | | 1–4.000 caracteres |
| `status` | text | no | `'queued'` | `queued`, `working`, `waiting_user`, `completed`, `failed`, `canceled` |
| `agent_snapshot` | jsonb | no | | Configuración del agente al crear la tarea |
| `created_at` | timestamptz | no | `now()` | |
| `parent_task_id` | uuid | sí | | Andamiaje para delegación entre agentes |
| `expected_output` | text | sí | | `docx`, `pptx` o `md` |
| `result_text` | text | sí | | Respuesta final del agente |
| `error` | jsonb | sí | | TaskError |
| `usage` | jsonb | sí | | TaskUsage; en el contrato se entrega en ceros si es nulo |
| `started_at` | timestamptz | sí | | Primera vez que pasa a `working` |
| `finished_at` | timestamptz | sí | | Al llegar a un estado final |

Índices: (`agent_id`, `status`) y (`workspace_id`, `created_at`).

### task_questions

| Columna | Tipo | Nulo | Por defecto | Notas |
|---|---|---|---|---|
| `id` | uuid | no | `gen_random_uuid()` | PK. Es el `question_id` |
| `workspace_id` | uuid | no | oficina por defecto | FK → workspaces |
| `task_id` | uuid | no | | FK → tasks |
| `question` | text | no | | Hasta 1.000 caracteres |
| `status` | text | no | `'pending'` | `pending`, `answered` o `expired` |
| `asked_at` | timestamptz | no | `now()` | |
| `options` | jsonb | sí | | Hasta 6 textos |
| `answer` | text | sí | | |
| `interrupt_id` | text | sí | | Id del interrupt de Strands, para reanudar |
| `answered_at` | timestamptz | sí | | |

Solo puede haber una pregunta `pending` por tarea (índice único parcial).

### artifacts

| Columna | Tipo | Nulo | Por defecto | Notas |
|---|---|---|---|---|
| `id` | uuid | no | `gen_random_uuid()` | PK |
| `workspace_id` | uuid | no | oficina por defecto | FK → workspaces |
| `task_id` | uuid | no | | FK → tasks |
| `agent_id` | uuid | no | | FK → agents |
| `type` | text | no | | `docx`, `pptx` o `md` |
| `status` | text | no | `'generating'` | `generating`, `ready` o `failed` |
| `created_at` | timestamptz | no | `now()` | |
| `title` | text | sí | | Título que le dio el agente |
| `mime` | text | sí | | Se deriva de `type` |
| `storage_path` | text | sí | | Se llena al quedar `ready` |
| `size_bytes` | bigint | sí | | |
| `source_spec` | jsonb | sí | | Contenido estructurado con el que se generó |
| `error` | jsonb | sí | | Si falló la generación |

### task_events

| Columna | Tipo | Nulo | Por defecto | Notas |
|---|---|---|---|---|
| `id` | bigint identity | no | automático | PK |
| `workspace_id` | uuid | no | oficina por defecto | FK → workspaces |
| `type` | text | no | | Tipo de mensaje o evento interno |
| `created_at` | timestamptz | no | `now()` | |
| `task_id` | uuid | sí | | FK → tasks |
| `agent_id` | uuid | sí | | FK → agents |
| `direction` | text | sí | | `in` (front → back), `out` (back → front) o null si es interno |
| `data` | jsonb | sí | | Contenido del mensaje |

Desde esta fase, los eventos internos de la fase 1 (`agent.created`, `agent.updated`, `agent.archived`) también se guardan en esta tabla.

### Storage

| Bucket | Privado | Ruta | Acceso |
|---|---|---|---|
| `artifacts` | sí | `{workspace_id}/{task_id}/{artifact_id}.{docx\|pptx\|md}` | URL firmada de 1 hora |

---

## 4. Protocolo WebSocket

El contrato completo está en la sección 5 del documento oficial. Resumen:

| Mensaje | Dirección | Data |
|---|---|---|
| `delegate` | front → back | `agent_id`, `instruction`, `expected_output` |
| `answer` | front → back | `task_id`, `question_id`, `answer` |
| `ask` | back → front | `question_id`, `question`, `options` |
| `finish` | back → front | `status`, `result_text`, `artifacts`, `error`, `usage` |
| `ack` | back → front | `task_id`, `status` |
| `error` | back → front | `code`, `message`, `details` |

### Validaciones

**delegate**

| Validación | Error |
|---|---|
| JSON válido, `type` conocido, `request_id` presente | `unknown_command` o `validation_error` |
| `agent_id` existe | `not_found` |
| El agente está activo | `agent_archived` |
| El servidor tiene API key del proveedor del agente | `provider_unavailable` |
| `instruction` de 1 a 4.000 caracteres; `expected_output` válido | `validation_error` |

**answer**

| Validación | Error |
|---|---|
| La tarea y la pregunta existen, y la pregunta es de esa tarea | `not_found` |
| La pregunta está `pending` y la tarea en `waiting_user` | `question_not_pending` |
| `answer` de 1 a 2.000 caracteres | `validation_error` |

### Entrega

- `ack` y `error` van solo a la conexión que envió el mensaje. `ask` y `finish` van a todas las conexiones.
- Al conectarse, cada cliente recibe los `ask` pendientes.
- Cada mensaje entrante y saliente se guarda en `task_events` con su `direction`.
- Si el front envía un `delegate` o `answer` mientras no hay otras conexiones, el `finish` o el `ask` se envían a quien esté conectado en ese momento. Si nadie lo está, quedan en la base: los `ask` pendientes se reenvían al reconectar. Los `finish` perdidos no se reenvían en esta fase; el front puede consultar el agente por REST.

---

## 5. Ejecución con Strands Agents

### Conexión a los modelos

Embers se conecta **directo** a la API de cada proveedor, con su API key. Sin Bedrock ni intermediarios.

| `model_config.provider` | Proveedor de Strands | Variable |
|---|---|---|
| `anthropic` | Proveedor de Anthropic | `ANTHROPIC_API_KEY` |
| `openai` | Proveedor de OpenAI | `OPENAI_API_KEY` |
| `gemini` | Proveedor de Gemini | `GEMINI_API_KEY` |

Los parámetros de `model_config.params` (temperatura, tokens máximos, top_p) se pasan al proveedor cuando no son nulos. Si son nulos, se usan los valores por defecto del proveedor.

### Cómo se arma el agente para cada tarea

A partir de `tasks.agent_snapshot` se construye un agente de Strands nuevo por tarea. Su system prompt tiene cuatro bloques, en este orden:

1. **Identidad:** nombre, rol, personalidad y tono.
2. **System prompt del agente:** el campo `instructions`, si no es nulo.
3. **Reglas de trabajo de Embers:**
   - Responde en el idioma de la instrucción.
   - Si falta información indispensable para hacer bien la tarea, usa `ask_user` una sola vez con una pregunta concreta y, si aplica, opciones. No preguntes lo que puedas decidir con un supuesto razonable.
   - Si la tarea pide un documento, una presentación o un archivo, usa la herramienta correspondiente.
   - Termina con un resumen breve de lo que hiciste.
4. **Formato esperado:** si la tarea trae `expected_output`, se le indica que debe entregar un archivo de ese tipo.

### Herramientas del agente

| Herramienta | Disponible | Qué recibe del modelo | Qué hace |
|---|---|---|---|
| `ask_user` | Siempre | `question` y `options` (opcional, hasta 6) | Pausa la tarea y le pregunta a la persona |
| `create_document` | Si está en `tools` | Título, resumen opcional y secciones: encabezado, párrafos, viñetas y una tabla opcional | Genera un .docx |
| `create_presentation` | Si está en `tools` | Título, subtítulo opcional y hasta 20 slides: título, viñetas y notas | Genera un .pptx, con una slide de portada y las de contenido |
| `create_markdown` | Si está en `tools` | Título y contenido en markdown | Genera un .md |

Las herramientas de archivos:

1. Crean el registro en `artifacts` en estado `generating`.
2. Generan el archivo con python-docx, python-pptx o directo en texto.
3. Lo suben a Storage y marcan el registro como `ready`.
4. Le devuelven al modelo el id, el título y el tipo del archivo.

Si la generación falla, marcan el registro como `failed` y le devuelven al modelo el error, para que decida si reintenta con otro contenido.

### Preguntas con interrupts de Strands

`ask_user` usa el mecanismo de interrupts de Strands:

1. La herramienta lanza un interrupt con la pregunta y las opciones.
2. El agente se detiene y devuelve el control con `stop_reason = "interrupt"`.
3. El backend guarda la pregunta en `task_questions` con el `interrupt_id`, pasa la tarea a `waiting_user` y envía `ask`.
4. **La instancia del agente queda en memoria**, en un registro por `task_id`. Es posible porque todo corre en local y en un solo proceso.
5. Con el `answer`, el backend reanuda esa misma instancia con la respuesta asociada al `interrupt_id`, y la tarea vuelve a `working`.

Límites:

- Hasta **3 preguntas por tarea**. A partir de la cuarta, `ask_user` no interrumpe y le responde al modelo que continúe con supuestos razonables y los mencione en su resumen.
- Si la pregunta no se responde en **30 minutos**, se marca `expired`, la tarea falla con `timeout` y se envía `finish`.
- Si el backend se reinicia, las instancias en memoria se pierden: las tareas abiertas pasan a `failed` con `internal_error`.

### Cola y concurrencia

- Cada agente atiende **una tarea a la vez**. Un `delegate` a un agente ocupado deja la tarea en `queued` y el `ack` lo indica.
- Las tareas en cola se atienden en orden de llegada.
- Una tarea en `waiting_user` **ocupa al agente**: la siguiente de su cola no empieza hasta que la actual termine.
- Distintos agentes trabajan en paralelo.

### Tiempos y errores

| Situación | Resultado |
|---|---|
| El trabajo del agente supera 10 minutos (sin contar la espera de respuestas) | `finish` fallido con `timeout` |
| El proveedor devuelve un error | `finish` fallido con `model_error`; el mensaje no incluye datos sensibles |
| `expected_output` pedía un archivo y no quedó ninguno de ese tipo en `ready` | `finish` fallido con `artifact_error`, con el `result_text` que haya |
| Error no previsto | `finish` fallido con `internal_error` |

En todos los casos la tarea guarda `error`, `finished_at` y el consumo que se alcanzó a medir, y el agente pasa a la siguiente tarea de su cola.

### Resultado

- `result_text` es el último mensaje del agente.
- `usage` suma los tokens de entrada, salida y total de toda la tarea, incluidas las reanudaciones, y guarda el `model_id`.
- `finish.artifacts` incluye todos los archivos `ready` de la tarea, con una URL firmada nueva.

---

## 6. Cambios en contratos existentes

| Contrato | Cambio en esta fase |
|---|---|
| `AgentOut.character_status` | Deja de ser siempre `idle`: `working` si tiene una tarea en `working`, `waiting` si tiene una en `waiting_user`, `idle` si no |
| `AgentOut.current_task_id` | La tarea en `working` o `waiting_user`, si existe |
| `AgentOut.queued_task_ids` | Las tareas en `queued`, en orden |
| `GET /artifacts/{id}/download` | Nuevo. Redirección 302 a una URL firmada nueva. `not_found` si no existe o no está `ready` |
| `DELETE /agents/{id}` | Si el agente tiene tareas abiertas, el archivado se permite y esas tareas continúan hasta terminar |

---

## 7. Configuración nueva

| Variable | Por defecto | Uso |
|---|---|---|
| `ARTIFACTS_BUCKET` | `artifacts` | Bucket de Storage |
| `SIGNED_URL_TTL_S` | `3600` | Vigencia de las URLs firmadas |
| `TASK_TIMEOUT_S` | `600` | Tiempo máximo de trabajo del agente |
| `ASK_TIMEOUT_S` | `1800` | Tiempo máximo de espera de una respuesta |
| `MAX_QUESTIONS_PER_TASK` | `3` | Límite de preguntas |
| `PPTX_TEMPLATE_PATH` | vacío | Plantilla .pptx opcional; sin ella se usa la plantilla por defecto de python-pptx |

---

## 8. Cómo se construye (OpenSpec)

Tres changes, en este orden:

| Change | Entrega |
|---|---|
| `add-realtime-gateway` | Endpoint `/ws`, sobre de mensajes, `ack` y `error`, validación de `delegate` y `answer`, registro de conexiones, reenvío de `ask` pendientes, guardado en `task_events`. Con un **runtime falso** que responde un `finish` fijo, para que el front pueda integrarse antes de tener el agente real |
| `add-agent-execution` | Tablas `tasks` y `task_questions`, cola por agente, runtime con Strands y proveedores directos, `ask_user` con interrupts, tiempos, errores, estado del personaje en `AgentOut` |
| `add-artifact-generation` | Tabla `artifacts`, bucket, herramientas `create_document`, `create_presentation` y `create_markdown`, subida a Storage, URLs firmadas, `GET /artifacts/{id}/download`, artefactos en `finish`, regla de `artifact_error` |

El runtime falso se activa con `AGENT_RUNTIME=fake` y queda disponible como plan B para el demo.

---

## 9. Criterios de aceptación

1. Un `delegate` válido a un agente libre recibe `ack` con `status: working` y, al terminar, todas las conexiones reciben `finish` con `status: completed` y `result_text`.
2. Un `delegate` a un agente archivado, inexistente o sin API key de su proveedor recibe `error` con el código correcto, y no se crea ninguna tarea.
3. Dos `delegate` seguidos al mismo agente: el primero recibe `working` y el segundo `queued`. El segundo empieza solo cuando llega el `finish` del primero.
4. Una instrucción ambigua ("hazme un informe") produce un `ask`. Tras el `answer`, el agente continúa y el `finish` refleja la respuesta.
5. Un `answer` a una pregunta ya respondida recibe `error` con `question_not_pending`.
6. Si el front se desconecta con un `ask` pendiente y se vuelve a conectar, recibe ese `ask` de nuevo.
7. Un `delegate` con `expected_output: pptx` termina con un `finish` que trae un artefacto pptx. Su `download_url` descarga un archivo que abre en PowerPoint.
8. Lo mismo con `docx` (abre en Word) y con `md`.
9. `GET /artifacts/{id}/download` redirige a una URL firmada vigente.
10. `GET /agents/{id}` muestra `character_status: working` durante la tarea, `waiting` con una pregunta pendiente e `idle` al terminar.
11. Una tarea que supera el tiempo máximo termina con `finish` fallido y `timeout`.
12. Los tres proveedores (Anthropic, OpenAI y Gemini) completan la misma tarea de prueba cuando tienen API key.
13. Cada mensaje del WebSocket queda en `task_events` con su dirección.
14. Con `AGENT_RUNTIME=fake`, el flujo `delegate` → `ack` → `finish` funciona sin llamar a ningún modelo.

---

## 10. Riesgos para el demo

| Riesgo | Mitigación |
|---|---|
| Latencia o caída del proveedor en vivo | Tener dos proveedores con API key y el runtime falso listo |
| El agente pregunta de más | La regla del prompt y el límite de 3 preguntas; probar las instrucciones del demo antes |
| Presentaciones con poco diseño | Configurar `PPTX_TEMPLATE_PATH` con una plantilla propia |
| Un archivo mal formado | Abrir cada archivo de prueba en Word y PowerPoint antes del demo |
