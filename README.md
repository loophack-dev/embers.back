# Embers backend

FastAPI backend for Embers. Phase 1: agent creation. Contracts: `docs/embers-modelos-y-contratos.md`.

## Requirements

- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- Docker (for the local Supabase stack)
- Node.js (the Supabase CLI runs through `npx supabase`)

## Run locally

```bash
uv sync
npx supabase start          # starts Postgres, Storage, etc. in Docker
npx supabase db reset       # applies supabase/migrations (creates the default workspace)
cp .env.example .env        # then set SUPABASE_SERVICE_ROLE_KEY:
npx supabase status -o env  #   copy SERVICE_ROLE_KEY from here
uv run embers               # http://localhost:3523
curl localhost:3523/health
```

`uv run embers` is equivalent to `uv run uvicorn embers.main:create_app --factory --port 3523`.

## Connect to a remote Supabase project

```bash
npx supabase login
npx supabase link --project-ref <project-ref>
npx supabase db push        # applies the migrations remotely
```

Then set in `.env`:

- `SUPABASE_URL=https://<project-ref>.supabase.co`
- `SUPABASE_SERVICE_ROLE_KEY` from Project Settings → API
- `DATABASE_URL` pointing to the **session-mode pooler (port 5432)**:
  `postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres`

## Configuration

See `.env.example`. `DEFAULT_WORKSPACE_ID` must stay `00000000-0000-0000-0000-000000000001` (the id seeded by the migration). Provider keys are optional; they only toggle availability.

## API

| Method | Path | Body | Response |
|---|---|---|---|
| GET | `/health` | — | HealthOut |
| GET | `/providers` | — | `{ items: ProviderOut[] }` |
| GET | `/tools` | — | `{ items: ToolOut[] }` |
| GET | `/agents?include_archived=false` | — | `{ items: AgentOut[] }` |
| POST | `/agents` | AgentCreate | AgentOut (201) |
| GET | `/agents/{id}` | — | AgentOut |
| PATCH | `/agents/{id}` | AgentUpdate | AgentOut |
| DELETE | `/agents/{id}` | — | 204 |
| PUT | `/agents/{id}/appearance` | AppearanceUpdate | AgentOut |

Errors always have the shape `{ "error": { "code", "message", "details" } }`. Writes publish
`agent.created`, `agent.updated` and `agent.archived` on the internal event bus (visible in the log).
The model catalog lives in `config/providers.yaml`; edit it and restart to change models.

### Examples

```bash
# Create a minimal agent
curl -X POST localhost:3523/agents -H 'Content-Type: application/json' -d '{
  "name": "Ana",
  "model_config": {"provider": "anthropic", "model_id": "claude-sonnet-5"},
  "identity": {"role": "Business analyst"}
}'

# Complete it (bumps version)
curl -X PATCH localhost:3523/agents/<id> -H 'Content-Type: application/json' -d '{
  "identity": {"role": "Business analyst", "persona": "Methodical", "tone": "Friendly"},
  "instructions": "Answer with short, actionable bullet points.",
  "model_config": {"provider": "anthropic", "model_id": "claude-sonnet-5", "params": {"temperature": 0.3}}
}'

# Save its appearance (does not bump version)
curl -X PUT localhost:3523/agents/<id>/appearance -H 'Content-Type: application/json' -d '{
  "data": {"avatar": "fox", "color": "#ff8800", "desk": {"x": 3, "y": 5}}
}'
```

## WebSocket (`ws://localhost:3523/ws`)

In: `delegate`, `answer`. Out: `ack` and `error` (only to the sender), `ask` and `finish` (to every
connection). Pending `ask` messages are re-sent on connect. Every message is stored in `task_events`.
`AGENT_RUNTIME=strands` (default) runs the agent with Strands Agents, directly against the agent's
provider (Anthropic, OpenAI or Gemini; the server needs that provider's API key). Each agent works
one task at a time (`ack` says `working` or `queued`); a task waiting for an `answer` keeps its
agent busy. Limits: `TASK_TIMEOUT_S` of agent work, `ASK_TIMEOUT_S` to answer a question,
`MAX_QUESTIONS_PER_TASK` questions per task. `GET /agents/{id}` shows `character_status`
(`idle`, `working`, `waiting`), `current_task_id` and `queued_task_ids`.

`AGENT_RUNTIME=fake` needs no API keys: the agent answers with a fixed text after
`FAKE_RUNTIME_DELAY_S`; an instruction containing "pregunta" triggers an `ask` first.

```bash
websocat ws://localhost:3523/ws   # or: uv run python -m websockets ws://localhost:3523/ws
```

```jsonc
// -> delegate
{"type": "delegate", "request_id": "r1", "data": {"agent_id": "<agent-id>", "instruction": "Tengo una pregunta sobre el informe", "expected_output": null}}
// <- ack
{"type": "ack", "event_id": 22, "ts": "...", "agent_id": "<agent-id>", "task_id": "<task-id>", "request_id": "r1", "data": {"task_id": "<task-id>", "status": "working"}}
// <- ask
{"type": "ask", "event_id": 23, "ts": "...", "agent_id": "<agent-id>", "task_id": "<task-id>", "request_id": null, "data": {"question_id": "<question-id>", "question": "¿Qué detalle quieres que tenga en cuenta?", "options": ["Formal", "Informal"]}}
// -> answer
{"type": "answer", "request_id": "r2", "data": {"task_id": "<task-id>", "question_id": "<question-id>", "answer": "Formal"}}
// <- ack {"status": "working"}, then finish
{"type": "finish", "event_id": 30, "ts": "...", "agent_id": "<agent-id>", "task_id": "<task-id>", "request_id": null, "data": {"status": "completed", "result_text": "Tarea completada por el runtime falso. Respuesta recibida: Formal", "artifacts": [], "error": null, "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "model_id": "gemini-3.8-flash"}}}
```

## Character status via Supabase Realtime

`agents.character_status` (`idle`, `working`, `waiting`) is kept by a database trigger on
`tasks` and the `agents` table is published to Supabase Realtime (it does not touch `updated_at`):

```ts
supabase
  .channel("agents")
  .on("postgres_changes", { event: "UPDATE", schema: "public", table: "agents" },
      (payload) => setStatus(payload.new.id, payload.new.character_status))
  .subscribe();
```

RLS is disabled for the demo, so anyone with the project's anon key receives these changes; enable
RLS with a read-only policy before exposing a remote project.

## Generated files

Agents with `create_document`, `create_presentation` or `create_markdown` in `tools` can generate
`.docx` (up to 30 sections), `.pptx` (cover + up to 20 slides, 6 bullets each) and `.md` files.
Files go to the private Storage bucket `ARTIFACTS_BUCKET` (created by the migrations) at
`{workspace_id}/{task_id}/{artifact_id}.{ext}`. `finish.artifacts` lists every ready file with a
signed `download_url` valid for `SIGNED_URL_TTL_S` seconds; `GET /artifacts/{id}/download`
redirects (302) to a fresh one. If `expected_output` is set and no file of that type is ready,
the task fails with `artifact_error`. Set `PPTX_TEMPLATE_PATH` to a `.pptx` to style
presentations (layout 0 = cover, layout 1 = title and content). With `AGENT_RUNTIME=fake`, a task
with `expected_output` gets a minimal file of that type.

When a file is ready, `artifacts.url` stores its Supabase Storage signed URL
(`{SUPABASE_URL}/storage/v1/object/sign/artifacts/...?token=...`) and `artifacts.url_expires_at` its
expiry, `ARTIFACT_URL_TTL_S` seconds later (default 7 days). `finish` sends the same URL and renews it
if it has expired.

## Lint

```bash
uv run ruff check . && uv run mypy src
```
