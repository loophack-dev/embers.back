# Embers · Fase 1: creación de agentes

**Objetivo:** la persona puede crear un agente con proveedor, identidad y system prompt, verlo, editarlo, darle apariencia y archivarlo. Todo queda persistido en Supabase y expuesto con los contratos REST oficiales.

**Documento de referencia:** `embers-modelos-y-contratos.md`. Si algo de esta fase contradice ese documento, manda el documento oficial. Las únicas precisiones de esta fase están en la sección 4 (qué campos aceptan nulos).

---

## 1. Alcance

### Incluido

| # | Capacidad | Resultado visible |
|---|---|---|
| 1 | Base del proyecto | El backend arranca, se conecta a Supabase y `GET /health` responde |
| 2 | Oficina por defecto | Existe una sola oficina con id fijo y todos los agentes pertenecen a ella |
| 3 | Catálogo de proveedores | `GET /providers` indica qué proveedores y modelos se pueden usar |
| 4 | Catálogo de herramientas | `GET /tools` lista las herramientas que se le pueden asignar a un agente |
| 5 | Crear agente | `POST /agents` guarda proveedor, identidad y system prompt |
| 6 | Consultar agentes | `GET /agents` y `GET /agents/{id}` |
| 7 | Editar agente | `PATCH /agents/{id}` con control de versión |
| 8 | Apariencia | `PUT /agents/{id}/appearance` guarda lo que define el front |
| 9 | Archivar agente | `DELETE /agents/{id}` lo archiva sin borrarlo |

### Fuera de esta fase

| Tema | Fase |
|---|---|
| WebSocket, eventos en vivo y snapshot de la oficina | Fase 2 |
| Ejecutar tareas con el modelo, artefactos y Storage | Fase 3 |
| Memoria y feedback | Fase 4 |
| Endpoints de memoria y descarga de artefactos | Fases 3 y 4 |
| Autenticación, varias oficinas | Después del hackatón |

Los eventos que el contrato asocia a cada endpoint (`agent.created`, `agent.updated`, `agent.archived`) sí se publican desde esta fase, pero en un **bus de eventos interno** que solo los registra en el log. La fase 2 conecta ese bus al WebSocket sin tocar los endpoints.

---

## 2. Qué es un agente en esta fase

| Parte | Campo | Obligatorio | Qué define |
|---|---|---|---|
| Nombre | `name` | sí | Cómo se llama en la oficina |
| Proveedor | `model_config` | sí | Proveedor, modelo y parámetros (temperatura, tokens) |
| Identidad | `identity` | sí (solo `role`) | Rol, personalidad y tono |
| System prompt | `instructions` | no | Cómo trabaja siempre el agente. Es el system prompt base; en la fase 3 se le suman la identidad, la memoria y la tarea |
| Herramientas | `tools` | no | Qué herramientas podrá usar. Si no se envía, recibe las tres del demo |
| Apariencia | `appearance` | no | Lo que el front necesita para dibujar el personaje |

En el contrato oficial el system prompt se llama `instructions`. Se mantiene ese nombre para no romper el contrato.

---

## 3. Modelo de datos de la fase

Esta fase crea solo las tablas que necesita: `workspaces`, `agents` y `ui_settings`. El resto de tablas del documento oficial se crea en su fase.

### Regla de nulos

- **No aceptan nulo** los campos mínimos para que un agente exista y pueda trabajar: `name`, `model_config`, `identity` y, dentro de ella, `role`. También los campos técnicos: ids, llaves foráneas, `status`, `version` y fechas.
- **Aceptan nulo** todos los demás: `instructions`, `tools`, `persona`, `tone`, los parámetros del modelo y la apariencia.
- La base guarda nulo cuando algo no se configuró. La API responde siempre con la forma del contrato (sección 4).

### workspaces

| Columna | Tipo | Nulo | Por defecto | Notas |
|---|---|---|---|---|
| `id` | uuid | no | `gen_random_uuid()` | PK |
| `name` | text | no | | |
| `created_at` | timestamptz | no | `now()` | |

La migración inserta la oficina por defecto con un id fijo (`DEFAULT_WORKSPACE_ID`) y el nombre "Oficina principal".

### agents

| Columna | Tipo | Nulo | Por defecto | Notas |
|---|---|---|---|---|
| `id` | uuid | no | `gen_random_uuid()` | PK |
| `workspace_id` | uuid | no | oficina por defecto | FK → workspaces |
| `name` | text | no | | 1–60 caracteres |
| `model_config` | jsonb | no | | Debe tener `provider` y `model_id`; `params` puede faltar |
| `identity` | jsonb | no | | Debe tener `role`; `persona` y `tone` pueden faltar |
| `instructions` | text | **sí** | | System prompt base, hasta 8.000 caracteres |
| `tools` | text[] | **sí** | | Ids de herramientas |
| `status` | text | no | `'active'` | `active` o `archived` |
| `version` | int | no | `1` | |
| `created_at` | timestamptz | no | `now()` | |
| `updated_at` | timestamptz | no | `now()` | Se actualiza con un trigger |

Restricciones:

- `status` solo acepta `active` o `archived`.
- `model_config` debe contener las llaves `provider` y `model_id`, e `identity` la llave `role` (check sobre el jsonb).
- El nombre es único entre los agentes activos de la misma oficina (índice único parcial con `status = 'active'`).

### ui_settings

| Columna | Tipo | Nulo | Por defecto | Notas |
|---|---|---|---|---|
| `id` | uuid | no | `gen_random_uuid()` | PK |
| `workspace_id` | uuid | no | oficina por defecto | FK → workspaces |
| `owner_type` | text | no | | `workspace` o `agent` |
| `owner_id` | uuid | no | | |
| `namespace` | text | no | | `appearance` en esta fase |
| `data` | jsonb | **sí** | | Máximo 64 KB |
| `updated_at` | timestamptz | no | `now()` | |

La combinación (`workspace_id`, `owner_type`, `owner_id`, `namespace`) es única.

---

## 4. De la base al contrato

La API respeta exactamente las formas de `AgentCreate`, `AgentUpdate`, `AgentOut` y `AppearanceUpdate` del documento oficial. Cuando un valor opcional está vacío en la base, se entrega así:

| Campo en la base | Si es nulo, la API responde | Motivo |
|---|---|---|
| `instructions` | `""` | El contrato define `instructions` como texto |
| `tools` | `[]` | El contrato define `tools` como lista |
| `identity.persona`, `identity.tone` | `null` | El contrato ya los admite como null |
| `model_config.params.*` | `null` en cada parámetro | El contrato ya los admite como null |
| apariencia sin registro o `data` nulo | `{}` | El contrato define `appearance` como objeto |

Al guardar ocurre lo inverso:

- Un `instructions` vacío (`""`) o no enviado se guarda como nulo.
- Si en la creación no se envían `tools`, se guardan las tres herramientas del demo, como indica el contrato. Si se envía una lista vacía, se guarda la lista vacía.

Campos de `AgentOut` que dependen de fases posteriores:

| Campo | Valor en fase 1 |
|---|---|
| `character_status` | Siempre `idle` |
| `current_task_id` | Siempre `null` |
| `queued_task_ids` | Siempre `[]` |

---

## 5. Contratos REST de la fase

Son los mismos del documento oficial. En esta fase no hay autenticación: el backend corre en local. El token estático opcional del documento oficial queda para una fase posterior, porque el contrato todavía no define su código de error.

| Método | Ruta | Entrada | Salida | Evento interno |
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

Todas las listas vienen en la forma `{ "items": [...] }`. Los errores vienen como `{ "error": { "code", "message", "details" } }`.

### Reglas de negocio

**Crear (`POST /agents`)**

- Valida el cuerpo contra AgentCreate.
- `model_config.provider` debe ser uno de los cuatro proveedores del contrato. `model_config.model_id` debe estar en el catálogo de ese proveedor (sección 6).
- Se puede crear un agente aunque el servidor no tenga API key de su proveedor: la falta de key solo impide ejecutar tareas (fase 3). En ese caso `GET /providers` muestra `available: false`.
- Cada id de `tools` debe existir en el catálogo de herramientas. Si no, responde `unknown_tool`.
- Si viene `appearance`, se guarda en `ui_settings` con `namespace = appearance`.
- Responde 201 con AgentOut y publica `agent.created`.

**Consultar (`GET /agents`, `GET /agents/{id}`)**

- La lista devuelve solo agentes activos, salvo con `include_archived=true`. Se ordena por fecha de creación.
- `GET /agents/{id}` devuelve también agentes archivados, con `status: archived`.

**Editar (`PATCH /agents/{id}`)**

- Solo cambia los campos enviados.
- `model_config` e `identity` se reemplazan completos cuando se envían; no se mezclan con los anteriores.
- Si cambia `model_config`, `identity`, `instructions` o `tools`, `version` sube en 1. Si solo cambia `name`, no sube.
- No se puede editar un agente archivado: responde `agent_archived`.
- Publica `agent.updated`.

**Apariencia (`PUT /agents/{id}/appearance`)**

- Reemplaza la apariencia completa. No sube `version`.
- Si pesa más de 64 KB, responde `validation_error`.
- Publica `agent.updated`.

**Archivar (`DELETE /agents/{id}`)**

- Cambia `status` a `archived`. No borra la fila.
- Si ya estaba archivado, responde 204 igual.
- Publica `agent.archived`.
- Después de archivarlo, su nombre queda libre para un agente nuevo.

**Salud (`GET /health`)**

- `db`: la consulta a Postgres responde.
- `storage`: la API de Storage de Supabase responde.
- `providers`: si cada proveedor tiene API key configurada.
- `status` es `ok` si `db` es verdadero; si no, `degraded`.

### Errores de la fase

| Código | HTTP | Cuándo |
|---|---|---|
| `validation_error` | 422 | El cuerpo no cumple el contrato, el modelo no está en el catálogo, el nombre ya existe entre los activos o la apariencia supera 64 KB. `details` indica el campo y el motivo |
| `unknown_tool` | 422 | Un id de `tools` no existe |
| `not_found` | 404 | El agente no existe |
| `agent_archived` | 409 | Se intenta editar o cambiar la apariencia de un agente archivado |
| `internal_error` | 500 | Error no previsto |

---

## 6. Catálogos

### Proveedores y modelos

El catálogo vive en un archivo de configuración del backend, para poder cambiar modelos sin tocar código. Cada modelo tiene `id` (el identificador del proveedor) y `label` (nombre visible). `available` se calcula según la variable de entorno de cada proveedor:

| Proveedor | Variable que lo habilita |
|---|---|
| `anthropic` | `ANTHROPIC_API_KEY` |
| `openai` | `OPENAI_API_KEY` |
| `gemini` | `GEMINI_API_KEY` |
| `bedrock` | `AWS_REGION` más credenciales de AWS |

Los ids de modelo concretos se definen al montar el proyecto, con los modelos vigentes de cada proveedor.

### Herramientas

En esta fase las herramientas solo se registran, con id, descripción y tipo de artefacto; su ejecución llega en la fase 3.

| id | Descripción | artifact_type |
|---|---|---|
| `create_document` | Genera un informe en Word | `docx` |
| `create_presentation` | Genera una presentación | `pptx` |
| `create_markdown` | Genera un documento de texto | `md` |

---

## 7. Configuración

| Variable | Obligatoria | Uso |
|---|---|---|
| `SUPABASE_URL` | sí | URL del proyecto de Supabase (local o remoto) |
| `SUPABASE_SERVICE_ROLE_KEY` | sí | Llave del backend para Storage y administración |
| `DATABASE_URL` | sí | Conexión a Postgres. En remoto, el pooler en modo sesión (puerto 5432) |
| `DEFAULT_WORKSPACE_ID` | sí | Id fijo de la oficina por defecto |
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `AWS_REGION` | no | Habilitan proveedores |
| `CORS_ORIGINS` | no | Orígenes permitidos para el front |

---

## 8. Cómo se construye (OpenSpec)

La fase se divide en dos changes, en este orden:

| Change | Capacidad | Entrega |
|---|---|---|
| `add-foundation` | proyecto | Estructura, configuración, conexión a Supabase, migración de `workspaces` con la oficina por defecto, bus de eventos interno, formato de errores, `GET /health` |
| `add-agent-crud` | agents | Migraciones de `agents` y `ui_settings`, catálogos, los ocho endpoints de agentes, proveedores y herramientas, con sus reglas y errores |

---

## 9. Criterios de aceptación

1. Las migraciones aplican limpias sobre un Supabase vacío, local o remoto, y la oficina por defecto existe.
2. `GET /health` responde `ok` con la base disponible.
3. Un agente creado solo con `name`, `model_config` (`provider` y `model_id`) e `identity` (`role`) se guarda. La fila tiene `instructions` nulo y la respuesta muestra `instructions: ""`, `appearance: {}` y las tres herramientas por defecto.
4. Un agente creado sin `model_config` o sin `identity.role` es rechazado con `validation_error`, y `details` indica el campo.
5. Un `model_id` que no está en el catálogo es rechazado con `validation_error`.
6. Un id de herramienta desconocido es rechazado con `unknown_tool`.
7. Editar `instructions` sube `version`; editar solo `name` no la sube.
8. Guardar la apariencia y luego leer el agente devuelve exactamente el mismo objeto.
9. Archivar un agente lo saca de `GET /agents` y libera su nombre. Editarlo después responde `agent_archived`.
10. Cada respuesta cumple el contrato oficial campo por campo; se verifica con tests de contrato.
11. Cada escritura publica su evento en el bus interno y se ve en el log.
