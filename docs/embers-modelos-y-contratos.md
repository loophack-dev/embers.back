# Embers · Modelos de datos y contratos

Alcance: demo del hackatón. Hay una sola oficina y la ejecución es local. El CRUD de agentes y memoria va por REST; la delegación de tareas y las preguntas del agente van por WebSocket, con cuatro mensajes: `delegate`, `answer`, `ask` y `finish`.

Este documento define tres capas:

| Capa | Qué es | Dónde vive | Quién la usa |
|---|---|---|---|
| **Base de datos** | Tablas en Supabase Postgres y el bucket de Storage | Migraciones SQL | Solo el backend |
| **Dominio** | Objetos que maneja el backend por dentro, igual que las filas más algunos objetos de valor | Backend | Solo el backend |
| **Contratos** | Lo que entra y sale por REST y WebSocket | Backend y front | Backend y front |

Convenciones para todo lo que ve el front:

- Los identificadores son UUID en texto.
- Las fechas van en ISO 8601, en UTC.
- Los nombres de campos van en `snake_case`.
- Un campo opcional sin valor llega como `null`; nunca se omite.
- El front nunca recibe columnas internas como `storage_path`, `workspace_id`, `agent_snapshot` o `source_spec`.

---

## 1. Enumeraciones

| Enum | Valores | Uso |
|---|---|---|
| **Provider** | `anthropic`, `openai`, `gemini`, `bedrock` | Proveedor del modelo de un agente |
| **AgentRecordStatus** | `active`, `archived` | Estado del registro del agente. Borrar un agente lo archiva |
| **CharacterStatus** | `idle`, `working`, `waiting` | Estado del personaje en la oficina. Se guarda en `agents.character_status`, lo mantiene la base a partir de las tareas y se publica en Supabase Realtime |
| **TaskStatus** | `queued`, `working`, `waiting_user`, `completed`, `failed`, `canceled` | Ciclo de vida de una tarea. `canceled` queda reservado |
| **QuestionStatus** | `pending`, `answered`, `expired` | Estado de una pregunta del agente a la persona |
| **MessageDirection** | `in`, `out` | Dirección de un mensaje WebSocket guardado en `task_events` |
| **ArtifactType** | `docx`, `pptx`, `md` | Tipos de archivo del demo |
| **ArtifactStatus** | `generating`, `ready`, `failed` | Estado de un artefacto |
| **MemoryKind** | `episodic`, `feedback`, `fact` | Tipo de memoria |
| **UiOwnerType** | `workspace`, `agent` | Dueño de una configuración visual |
| **ErrorCode** | ver §6 | Códigos de error de REST y WebSocket |

### Estado del personaje (CharacterStatus)

| Estado | Cuándo | Animación sugerida |
|---|---|---|
| `idle` | El agente no tiene una tarea en `working` ni en `waiting_user` | En su escritorio |
| `working` | Tiene una tarea en `working` | Tecleando |
| `waiting` | Tiene una tarea en `waiting_user` | Esperando a la persona |

### Transiciones de una tarea (TaskStatus)

| Desde | Hacia | Qué la provoca |
|---|---|---|
| `queued` | `working` | El agente queda libre y toma la tarea |
| `working` | `waiting_user` | El agente usa `ask_user`; se envía `ask` |
| `waiting_user` | `working` | Llega el `answer` de la pregunta pendiente |
| `working` | `completed` | El agente termina; se envía `finish` |
| `working` | `failed` | Error del modelo, `timeout`, `artifact_error` o error no previsto; se envía `finish` |
| `waiting_user` | `failed` | La pregunta vence sin respuesta (`timeout`); se envía `finish` |

Los estados `completed`, `failed` y `canceled` son finales. Si el backend se reinicia, las tareas en `queued`, `working` o `waiting_user` pasan a `failed` con el código `internal_error`.

---

## 2. Base de datos (Supabase)

Hay ocho tablas en el esquema `public`. Todas llevan `workspace_id`, que apunta a la oficina por defecto; es el andamiaje para tener varias oficinas más adelante. RLS está desactivado en el demo porque solo el backend accede a la base.

### workspaces

| Columna | Tipo | Nulo | Por defecto | Notas |
|---|---|---|---|---|
| `id` | uuid | no | `gen_random_uuid()` | PK. La oficina por defecto tiene un id fijo, definido en la configuración |
| `name` | text | no | | "Oficina principal" |
| `created_at` | timestamptz | no | `now()` | |

### agents

| Columna | Tipo | Nulo | Por defecto | Notas |
|---|---|---|---|---|
| `id` | uuid | no | `gen_random_uuid()` | PK |
| `workspace_id` | uuid | no | | FK → workspaces |
| `name` | text | no | | 1–60 caracteres, único por oficina entre los agentes activos |
| `model_config` | jsonb | no | | Objeto ModelConfig (§3) |
| `identity` | jsonb | no | | Objeto AgentIdentity (§3) |
| `instructions` | text | no | `''` | Hasta 8.000 caracteres. Cómo trabaja siempre el agente |
| `tools` | text[] | no | `{}` | Ids de herramientas registradas |
| `status` | text | no | `'active'` | AgentRecordStatus |
| `character_status` | text | no | `'idle'` | CharacterStatus. Lo mantiene un trigger sobre `tasks`; no modifica `updated_at`. `agents` está publicada en Supabase Realtime |
| `version` | int | no | `1` | Sube al cambiar `model_config`, `identity`, `instructions` o `tools` |
| `created_at` | timestamptz | no | `now()` | |
| `updated_at` | timestamptz | no | `now()` | Se actualiza con un trigger |

### ui_settings

Aquí se guarda la configuración visual que define el front. El backend la guarda tal cual y no la interpreta.

| Columna | Tipo | Nulo | Por defecto | Notas |
|---|---|---|---|---|
| `id` | uuid | no | `gen_random_uuid()` | PK |
| `workspace_id` | uuid | no | | FK → workspaces |
| `owner_type` | text | no | | UiOwnerType |
| `owner_id` | uuid | no | | Id del agente o de la oficina |
| `namespace` | text | no | | `appearance` para agentes, `office` para la oficina |
| `data` | jsonb | no | `{}` | Máximo 64 KB |
| `updated_at` | timestamptz | no | `now()` | |

La combinación (`workspace_id`, `owner_type`, `owner_id`, `namespace`) es única.

### tasks

| Columna | Tipo | Nulo | Por defecto | Notas |
|---|---|---|---|---|
| `id` | uuid | no | `gen_random_uuid()` | PK |
| `workspace_id` | uuid | no | | FK → workspaces |
| `agent_id` | uuid | no | | FK → agents |
| `parent_task_id` | uuid | sí | | FK → tasks. Andamiaje para delegación; en el demo siempre es null |
| `instruction` | text | no | | 1–4.000 caracteres. Lo que pidió la persona |
| `expected_output` | text | sí | | ArtifactType; null si decide el agente |
| `status` | text | no | `'queued'` | TaskStatus |
| `result_text` | text | sí | | Respuesta final del agente (último mensaje) |
| `error` | jsonb | sí | | Objeto TaskError (§3) |
| `usage` | jsonb | no | `{}` | Objeto TaskUsage (§3) |
| `agent_snapshot` | jsonb | no | | Objeto AgentSnapshot (§3): la configuración del agente al crear la tarea |
| `created_at` | timestamptz | no | `now()` | |
| `started_at` | timestamptz | sí | | Cuando pasa a `working` |
| `finished_at` | timestamptz | sí | | Cuando llega a un estado final |

Índices: (`agent_id`, `created_at`) y (`workspace_id`, `status`).

### task_questions

Preguntas del agente a la persona (herramienta `ask_user`).

| Columna | Tipo | Nulo | Por defecto | Notas |
|---|---|---|---|---|
| `id` | uuid | no | `gen_random_uuid()` | PK. Es el `question_id` |
| `workspace_id` | uuid | no | | FK → workspaces |
| `task_id` | uuid | no | | FK → tasks |
| `question` | text | no | | 1–1.000 caracteres |
| `options` | jsonb | sí | | Lista de hasta 6 textos |
| `status` | text | no | `'pending'` | QuestionStatus |
| `answer` | text | sí | | 1–2.000 caracteres |
| `interrupt_id` | text | sí | | Id del interrupt de Strands, para reanudar |
| `asked_at` | timestamptz | no | `now()` | |
| `answered_at` | timestamptz | sí | | |

Solo puede haber una pregunta `pending` por tarea (índice único parcial).

### task_events

Registro de cada mensaje WebSocket que entra o sale, y de los eventos internos (`agent.created`, `agent.updated`, `agent.archived`).

| Columna | Tipo | Nulo | Por defecto | Notas |
|---|---|---|---|---|
| `id` | bigint identity | no | automático | PK. Es el `event_id` que ve el front |
| `workspace_id` | uuid | no | | FK → workspaces |
| `task_id` | uuid | sí | | FK → tasks |
| `agent_id` | uuid | sí | | FK → agents |
| `type` | text | no | | Tipo de mensaje (§5) o de evento interno |
| `direction` | text | sí | | MessageDirection; null en los eventos internos |
| `data` | jsonb | no | `{}` | Mensaje completo sin `event_id` ni `ts` (son el `id` y el `created_at` de la fila), o datos del evento interno |
| `created_at` | timestamptz | no | `now()` | Es el `ts` del mensaje |

Índice: (`workspace_id`, `id`).

### artifacts

| Columna | Tipo | Nulo | Por defecto | Notas |
|---|---|---|---|---|
| `id` | uuid | no | `gen_random_uuid()` | PK |
| `workspace_id` | uuid | no | | FK → workspaces |
| `task_id` | uuid | no | | FK → tasks |
| `agent_id` | uuid | no | | FK → agents |
| `title` | text | no | | Título que le dio el agente |
| `type` | text | no | | ArtifactType |
| `mime` | text | no | | Se deriva de `type` |
| `status` | text | no | `'generating'` | ArtifactStatus |
| `storage_path` | text | sí | | Ruta en Storage; se llena al quedar `ready` |
| `size_bytes` | bigint | sí | | |
| `source_spec` | jsonb | sí | | Contenido estructurado con el que se generó; permite regenerar el archivo |
| `url` | text | sí | | URL firmada de Supabase Storage (`/storage/v1/object/sign/artifacts/...?token=...`); se llena al quedar `ready` y vence a los `ARTIFACT_URL_TTL_S` segundos (7 días por defecto) |
| `url_expires_at` | timestamptz | sí | | Vencimiento de `url`. Si vence, el siguiente `finish` que la entregue la renueva |
| `created_at` | timestamptz | no | `now()` | |

### memories

| Columna | Tipo | Nulo | Por defecto | Notas |
|---|---|---|---|---|
| `id` | uuid | no | `gen_random_uuid()` | PK |
| `workspace_id` | uuid | no | | FK → workspaces |
| `agent_id` | uuid | no | | FK → agents |
| `kind` | text | no | | MemoryKind |
| `content` | text | no | | 1–2.000 caracteres |
| `source_task_id` | uuid | sí | | FK → tasks |
| `pinned` | boolean | no | `false` | Si es true, siempre entra al prompt |
| `embedding` | vector(1536) | sí | | Andamiaje; null en el demo |
| `created_at` | timestamptz | no | `now()` | |
| `updated_at` | timestamptz | no | `now()` | Se actualiza con un trigger |

Índice: (`agent_id`, `created_at` descendente).

### Storage

| Bucket | Privado | Ruta del archivo | Acceso del front |
|---|---|---|---|
| `artifacts` | sí | `{workspace_id}/{task_id}/{artifact_id}.{docx\|pptx\|md}` | URL firmada que dura 1 hora. Llega en `download_url`; si vence, se renueva con `GET /artifacts/{id}/download` |

### Relaciones

| Relación | Cardinalidad | Al borrar el padre |
|---|---|---|
| workspace → agents, tasks, artifacts, memories, ui_settings, task_events | 1 a N | Borrado en cascada |
| agent → tasks | 1 a N | Se bloquea; el agente se archiva, no se borra |
| agent → memories | 1 a N | Borrado en cascada |
| task → artifacts | 1 a N | Borrado en cascada |
| task → task_events | 1 a N | Borrado en cascada |
| task → task_questions | 1 a N | Borrado en cascada |
| task → memories (`source_task_id`) | 1 a N | Queda en null |
| task → tasks (`parent_task_id`) | 1 a N | Andamiaje |

---

## 3. Objetos de valor

Estos objetos se guardan dentro de columnas jsonb y viajan igual en los contratos.

### ModelConfig

| Campo | Tipo | Obligatorio | Notas |
|---|---|---|---|
| `provider` | Provider | sí |  |
| `model_id` | texto | sí | 1–120 caracteres. Debe estar en la lista de `GET /providers` |
| `params` | ModelParams | no |  |

### ModelParams

| Campo | Tipo | Obligatorio | Notas |
|---|---|---|---|
| `temperature` | número \| null | no | ≥ 0 y ≤ 2 |
| `max_tokens` | entero \| null | no | ≥ 256 y ≤ 64000 |
| `top_p` | número \| null | no | > 0 y ≤ 1 |

### AgentIdentity

| Campo | Tipo | Obligatorio | Notas |
|---|---|---|---|
| `role` | texto | sí | 1–80 caracteres. Rol en la oficina, p. ej. 'Analista de negocio' |
| `persona` | texto \| null | no | 0–600 caracteres. Personalidad y forma de ser |
| `tone` | texto \| null | no | 0–120 caracteres. Tono al comunicarse |

### Appearance

Lo define el front y el backend lo guarda sin validarlo por dentro. Solo verifica que sea un objeto de hasta 64 KB. La forma sugerida es:

| Campo | Tipo | Notas |
|---|---|---|
| `avatar` | texto | Id del sprite o personaje |
| `color` | texto | Color en hexadecimal |
| `desk` | objeto `{x, y}` | Posición en la oficina |

### TaskUsage

| Campo | Tipo | Obligatorio | Notas |
|---|---|---|---|
| `input_tokens` | entero | no | Por defecto `0` |
| `output_tokens` | entero | no | Por defecto `0` |
| `total_tokens` | entero | no | Por defecto `0` |
| `model_id` | texto \| null | no |  |

### TaskError

| Campo | Tipo | Obligatorio | Notas |
|---|---|---|---|
| `code` | ErrorCode | sí |  |
| `message` | texto | sí |  |
| `retryable` | booleano | no | Por defecto `false` |

### AgentSnapshot (solo backend)

Es una copia de la configuración del agente en el momento de crear la tarea. Si el agente se edita después, la tarea sigue mostrando con qué configuración se hizo.

| Campo | Tipo | Obligatorio | Notas |
|---|---|---|---|
| `name` | texto | sí |  |
| `version` | entero | sí |  |
| `model_config` | ModelConfig | sí |  |
| `identity` | AgentIdentity | sí |  |
| `instructions` | texto | sí |  |
| `tools` | lista de texto | sí |  |

---

## 4. Contratos REST

La URL base en local es `http://localhost:3523`. No hay autenticación en el demo; puede activarse un token estático opcional en el header `Authorization`.

| Método | Ruta | Entrada | Salida | Evento interno (se guarda en `task_events`) |
|---|---|---|---|---|
| GET | `/health` | — | HealthOut | — |
| GET | `/providers` | — | lista de ProviderOut | — |
| GET | `/tools` | — | lista de ToolOut | — |
| GET | `/agents` | `?include_archived=false` | lista de AgentOut | — |
| POST | `/agents` | AgentCreate | AgentOut (201) | `agent.created` |
| GET | `/agents/{id}` | — | AgentOut | — |
| PATCH | `/agents/{id}` | AgentUpdate | AgentOut | `agent.updated` |
| DELETE | `/agents/{id}` | — | 204 | `agent.archived` |
| PUT | `/agents/{id}/appearance` | AppearanceUpdate | AgentOut | `agent.updated` |
| GET | `/agents/{id}/memories` | `?kind=` | lista de MemoryOut | — |
| POST | `/agents/{id}/memories` | MemoryCreate | MemoryOut (201) | `memory.saved` |
| PATCH | `/agents/{id}/memories/{memory_id}` | MemoryUpdate | MemoryOut | `memory.saved` |
| DELETE | `/agents/{id}/memories/{memory_id}` | — | 204 | `memory.deleted` |
| GET | `/artifacts/{id}/download` | — | Redirección 302 a la URL firmada | — |

Todas las listas vienen en la forma `{ "items": [...] }`.

### AgentCreate

| Campo | Tipo | Obligatorio | Notas |
|---|---|---|---|
| `name` | texto | sí | 1–60 caracteres |
| `model_config` | ModelConfig | sí | Ver ModelConfig |
| `identity` | AgentIdentity | sí | Ver AgentIdentity |
| `instructions` | texto | no | Por defecto `""`. 0–8000 caracteres |
| `tools` | lista de texto | no | Por defecto las tres herramientas del demo. Cada id debe existir en `GET /tools` |
| `appearance` | objeto \| null | no | Se guarda en ui_settings (namespace appearance) |

### AgentUpdate

Actualización parcial: solo se cambian los campos enviados. La apariencia se actualiza aparte, con `PUT /agents/{id}/appearance`.

| Campo | Tipo | Obligatorio | Notas |
|---|---|---|---|
| `name` | texto \| null | no | 1–60 caracteres |
| `model_config` | ModelConfig \| null | no |  |
| `identity` | AgentIdentity \| null | no |  |
| `instructions` | texto \| null | no | 0–8000 caracteres |
| `tools` | lista de texto \| null | no |  |

### AgentOut

| Campo | Tipo | Obligatorio | Notas |
|---|---|---|---|
| `id` | uuid | sí |  |
| `name` | texto | sí |  |
| `model_config` | ModelConfig | sí |  |
| `identity` | AgentIdentity | sí |  |
| `instructions` | texto | sí |  |
| `tools` | lista de texto | sí |  |
| `status` | AgentRecordStatus | sí |  |
| `version` | entero | sí | Sube al cambiar modelo, identidad, instrucciones o tools |
| `appearance` | objeto | sí | `{}` si no se ha guardado |
| `character_status` | CharacterStatus | sí | Estado actual del personaje |
| `current_task_id` | uuid \| null | sí | Tarea en curso, si hay |
| `queued_task_ids` | lista de uuid | sí | Tareas en espera para este agente |
| `created_at` | fecha-hora | sí |  |
| `updated_at` | fecha-hora | sí |  |

### AppearanceUpdate

Reemplaza la apariencia completa.

| Campo | Tipo | Obligatorio | Notas |
|---|---|---|---|
| `data` | objeto | sí |  |

### MemoryCreate

Las memorias `episodic` solo las crea el backend. El front puede crear `fact` y `feedback`.

| Campo | Tipo | Obligatorio | Notas |
|---|---|---|---|
| `kind` | fact \| feedback | no | Por defecto `"fact"` |
| `content` | texto | sí | 1–2000 caracteres |
| `pinned` | booleano | no | Por defecto `false` |

### MemoryUpdate

| Campo | Tipo | Obligatorio | Notas |
|---|---|---|---|
| `content` | texto \| null | no | 1–2000 caracteres |
| `pinned` | booleano \| null | no |  |

### MemoryOut

| Campo | Tipo | Obligatorio | Notas |
|---|---|---|---|
| `id` | uuid | sí |  |
| `agent_id` | uuid | sí |  |
| `kind` | MemoryKind | sí |  |
| `content` | texto | sí |  |
| `pinned` | booleano | sí | Si es true, siempre entra al prompt |
| `source_task_id` | uuid \| null | sí | Tarea que originó la memoria (episodic y feedback) |
| `created_at` | fecha-hora | sí |  |
| `updated_at` | fecha-hora | sí |  |

### ProviderOut

| Campo | Tipo | Obligatorio | Notas |
|---|---|---|---|
| `provider` | Provider | sí |  |
| `available` | booleano | sí | False si falta la API key en el servidor |
| `models` | lista de ProviderModelOut | sí |  |

### ProviderModelOut

| Campo | Tipo | Obligatorio | Notas |
|---|---|---|---|
| `id` | texto | sí |  |
| `label` | texto | sí |  |

### ToolOut

| Campo | Tipo | Obligatorio | Notas |
|---|---|---|---|
| `id` | texto | sí |  |
| `description` | texto | sí |  |
| `artifact_type` | ArtifactType \| null | no |  |

Herramientas del demo:

| id | Qué hace | artifact_type |
|---|---|---|
| `create_document` | Genera un informe en Word | `docx` |
| `create_presentation` | Genera una presentación | `pptx` |
| `create_markdown` | Genera un documento de texto | `md` |

### HealthOut

| Campo | Tipo | Obligatorio | Notas |
|---|---|---|---|
| `status` | ok \| degraded | sí |  |
| `db` | booleano | sí |  |
| `storage` | booleano | sí |  |
| `providers` | objeto | sí |  |

---

## 5. Contratos WebSocket

La conexión es `ws://localhost:3523/ws`. Todos los mensajes son JSON. El protocolo tiene solo seis mensajes: entran `delegate` y `answer`; salen `ack`, `error`, `ask` y `finish`. No hay eventos de progreso ni streaming.

### Sobre de los mensajes

**Cliente → servidor**

| Campo | Tipo | Obligatorio | Notas |
|---|---|---|---|
| `type` | `delegate` \| `answer` | sí | |
| `request_id` | texto | sí | 1–64 caracteres. Lo genera el front y vuelve en el `ack` o el `error` |
| `data` | objeto | sí | Depende del tipo |

**Servidor → cliente**

| Campo | Tipo | Obligatorio | Notas |
|---|---|---|---|
| `type` | `ack` \| `error` \| `ask` \| `finish` | sí | |
| `event_id` | entero | sí | Id del mensaje en `task_events` |
| `ts` | fecha-hora | sí | Momento del mensaje |
| `agent_id` | uuid \| null | sí | Agente relacionado |
| `task_id` | uuid \| null | sí | Tarea relacionada |
| `request_id` | texto \| null | sí | Id del mensaje al que responde en `ack` y `error`; null en `ask` y `finish`, y en `error` si no se pudo leer |
| `data` | objeto | sí | Depende del tipo |

### Mensajes

| type | Dirección | data | Entrega |
|---|---|---|---|
| `delegate` | cliente → servidor | DelegateData | — |
| `answer` | cliente → servidor | AnswerData | — |
| `ack` | servidor → cliente | AckData | Solo a la conexión que envió el mensaje |
| `error` | servidor → cliente | ErrorBody (§6) | Solo a la conexión que envió el mensaje |
| `ask` | servidor → cliente | AskData | A todas las conexiones |
| `finish` | servidor → cliente | FinishData | A todas las conexiones |

### Reglas de entrega

1. Al abrir la conexión, el servidor envía a ese cliente los `ask` de las preguntas `pending`, en orden de creación.
2. `ask` y `finish` se envían a las conexiones abiertas en ese momento. Si no hay ninguna, quedan en la base: los `ask` pendientes se reenvían al reconectar; los `finish` no se reenvían (el front consulta el agente por REST).
3. Cada mensaje que entra o sale se guarda en `task_events` con su `direction`.

### Secuencia típica de una tarea

| # | Mensaje | Detalle |
|---|---|---|
| 1 | `delegate` | El front pide la tarea |
| 2 | `ack` | Trae el `task_id` y `status: working` (o `queued` si el agente está ocupado) |
| 3 | `ask` | Opcional: el agente necesita información |
| 4 | `answer` | El front responde; recibe `ack` con `status: working` |
| 5 | `finish` | Resultado, archivos y consumo |

### Objetos de los mensajes

#### DelegateData

| Campo | Tipo | Obligatorio | Notas |
|---|---|---|---|
| `agent_id` | uuid | sí | Agente activo |
| `instruction` | texto | sí | 1–4000 caracteres |
| `expected_output` | ArtifactType \| null | no | Por defecto null; si viene, el agente debe entregar un archivo de ese tipo |

#### AnswerData

| Campo | Tipo | Obligatorio | Notas |
|---|---|---|---|
| `task_id` | uuid | sí | |
| `question_id` | uuid | sí | |
| `answer` | texto | sí | 1–2000 caracteres |

#### AckData

| Campo | Tipo | Obligatorio | Notas |
|---|---|---|---|
| `task_id` | uuid | sí | |
| `status` | `working` \| `queued` | sí | Estado de la tarea después del mensaje |

#### AskData

| Campo | Tipo | Obligatorio | Notas |
|---|---|---|---|
| `question_id` | uuid | sí | |
| `question` | texto | sí | 1–1000 caracteres |
| `options` | lista de texto \| null | sí | Hasta 6; null si la respuesta es libre |

#### FinishData

| Campo | Tipo | Obligatorio | Notas |
|---|---|---|---|
| `status` | `completed` \| `failed` | sí | |
| `result_text` | texto \| null | sí | Último mensaje del agente |
| `artifacts` | lista de ArtifactOut | sí | Archivos `ready` de la tarea, con URL firmada nueva |
| `error` | TaskError \| null | sí | null si `completed` |
| `usage` | TaskUsage | sí | Consumo acumulado de la tarea; ceros si no hubo |

#### ArtifactOut

| Campo | Tipo | Obligatorio | Notas |
|---|---|---|---|
| `id` | uuid | sí |  |
| `task_id` | uuid | sí |  |
| `agent_id` | uuid | sí |  |
| `title` | texto | sí |  |
| `type` | ArtifactType | sí |  |
| `mime` | texto | sí |  |
| `status` | ArtifactStatus | sí |  |
| `size_bytes` | entero \| null | sí | null mientras se genera |
| `download_url` | texto \| null | sí | URL firmada; null mientras status != ready |
| `url_expires_at` | fecha-hora \| null | sí |  |
| `created_at` | fecha-hora | sí |  |

### Validaciones y errores de WebSocket

| Mensaje | Validación | Código |
|---|---|---|
| cualquiera | JSON inválido o `type` desconocido | `unknown_command` |
| cualquiera | Falta `request_id` o `data`, o no cumplen el contrato | `validation_error` |
| `delegate` | `agent_id` no existe | `not_found` |
| `delegate` | El agente está archivado | `agent_archived` |
| `delegate` | El servidor no tiene API key del proveedor del agente | `provider_unavailable` |
| `delegate` | `instruction` fuera de 1–4000 o `expected_output` inválido | `validation_error` |
| `answer` | La tarea o la pregunta no existen, o la pregunta no es de esa tarea | `not_found` |
| `answer` | La pregunta no está `pending` o la tarea no está en `waiting_user` | `question_not_pending` |
| `answer` | `answer` fuera de 1–2000 | `validation_error` |

Un mensaje rechazado no crea ni cambia nada.

---

## 6. Errores

En REST, los errores llegan en la forma `{ "error": ErrorBody }`. En WebSocket llegan como un evento `error`, cuyo `data` es un ErrorBody.

### ErrorBody

| Campo | Tipo | Obligatorio | Notas |
|---|---|---|---|
| `code` | ErrorCode | sí |  |
| `message` | texto | sí |  |
| `details` | objeto \| null | no |  |

| Código | HTTP | Cuándo |
|---|---|---|
| `validation_error` | 422 | La entrada no cumple el contrato; `details` indica los campos |
| `not_found` | 404 | No existe el agente, la tarea, la memoria o el artefacto |
| `agent_archived` | 409 | Se intenta editar un agente archivado o delegarle una tarea |
| `provider_unavailable` | 409 | El proveedor del agente no tiene API key configurada en el servidor |
| `unknown_tool` | 422 | Un id de `tools` no existe |
| `task_not_cancelable` | 409 | Reservado: la tarea ya está en un estado final |
| `question_not_pending` | — | Solo WebSocket: la pregunta ya no está `pending` o la tarea no está en `waiting_user` |
| `unknown_command` | — | Solo WebSocket: JSON inválido o `type` desconocido |
| `model_error` | — | Solo en `finish.error`: el proveedor devolvió un error |
| `timeout` | — | Solo en `finish.error`: el trabajo superó 10 minutos o la pregunta venció sin respuesta |
| `artifact_error` | — | Solo en `finish.error`: se pidió un archivo (`expected_output`) y no quedó ninguno de ese tipo listo |
| `internal_error` | 500 | Error no previsto |

---

## 7. Qué queda preparado para después

| Elemento | Hoy | Después |
|---|---|---|
| `workspace_id` en todas las tablas | Una oficina fija | Varias oficinas, con miembros y RLS |
| `tasks.parent_task_id` | Siempre null | Delegación entre agentes |
| `memories.embedding` | Siempre null | Búsqueda semántica de memorias |
| `ui_settings` con `owner_type = workspace` | Sin uso | Distribución y tema de la oficina |
| `artifacts.source_spec` | Se guarda | Regenerar archivos y crear versiones |
