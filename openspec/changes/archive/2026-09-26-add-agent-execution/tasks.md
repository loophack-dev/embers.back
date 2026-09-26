# Tasks

## 1. Configuración y dependencia

- [x] 1.1 Agregar `strands-agents[anthropic,openai,gemini]==1.57.1`; `AGENT_RUNTIME` acepta `strands|fake` (por defecto `strands`), y agregar `TASK_TIMEOUT_S`, `ASK_TIMEOUT_S` y `MAX_QUESTIONS_PER_TASK` a `Settings` y `.env.example`; verificar con `uv sync` y `mypy`

## 2. Runtime de Strands

- [x] 2.1 Implementar `domain/prompt.py` (cuatro bloques) y verificar a mano el prompt de un agente con y sin `instructions`
- [x] 2.2 Implementar `runtime/strands_runtime.py` (`build_model`, `ask_user` con límite, `start`, `resume`, `discard`, delta de consumo, mapeo de errores a `ModelProviderError`) y registrarlo en `runtime/factory.py`; verificar con `grep` que ningún otro módulo importa `strands` y con `mypy`

## 3. Cola, tiempos y estado

- [x] 3.1 Agregar a `TaskService` la cola por agente (`working`/`queued` en el `ack`, siguiente tarea al terminar), el presupuesto `TASK_TIMEOUT_S` por tramos, el vencimiento de preguntas y el mapeo de `ModelProviderError`/`TimeoutError` a `finish` fallido
- [x] 3.2 Implementar el estado del personaje en `AgentOut` (`open_tasks` en el repositorio, `to_agent_out` y `CharacterStatus` = `idle|working|waiting`)

## 4. Verificación y documentación

- [x] 4.1 Verificar a mano con `AGENT_RUNTIME=fake` y tiempos cortos: cola (CA3), `character_status` (CA10), vencimiento de pregunta y `timeout` (CA11), `provider_unavailable` con `strands` (CA2)
- [x] 4.2 Verificar con `AGENT_RUNTIME=strands` los proveedores con API key (CA1, CA4, CA12) o dejar constancia de cuáles no se pudieron probar (constancia: el `.env` no tiene API keys; se verificó la conexión directa a Anthropic con una key inválida → `model_error` `AuthenticationError`, y el flujo de interrupts con un modelo guionado sin red. CA1, CA4 y CA12 quedan pendientes de keys reales); actualizar `README.md`; `ruff` y `mypy` sin errores
