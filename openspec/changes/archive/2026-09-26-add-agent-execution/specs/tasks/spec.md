# Spec Delta

## ADDED Requirements

### Requirement: Cola por agente
Cada agente SHALL atender una tarea a la vez, en orden de llegada. Una tarea delegada a un agente con una tarea en `working` o `waiting_user`, o con tareas en cola, MUST crearse en `queued`; en otro caso, en `working`. Al terminar la tarea actual (`completed` o `failed`), el agente MUST empezar la siguiente de su cola. Una tarea en `waiting_user` MUST seguir ocupando al agente. Agentes distintos MUST trabajar en paralelo.

#### Scenario: CA3 · Dos delegate seguidos
- **WHEN** se envían dos `delegate` seguidos al mismo agente libre
- **THEN** el primero recibe `ack` con `working`, el segundo con `queued`, y el segundo pasa a `working` solo después del `finish` del primero

#### Scenario: Pregunta ocupa al agente
- **WHEN** la tarea actual está en `waiting_user` y llega otro `delegate` al mismo agente
- **THEN** la nueva tarea queda `queued` hasta que la actual termine

### Requirement: Preguntas a la persona
Cuando el agente usa `ask_user`, la tarea SHALL guardar la pregunta con su `interrupt_id`, pasar a `waiting_user` y enviar `ask`. Con el `answer`, MUST reanudarse la misma instancia del agente con la respuesta asociada al `interrupt_id` y la tarea MUST volver a `working`. Desde la pregunta número `MAX_QUESTIONS_PER_TASK + 1` (por defecto la cuarta), `ask_user` MUST NOT interrumpir y MUST responder al modelo que continúe con supuestos razonables y los mencione en su resumen.

#### Scenario: CA4 · Instrucción ambigua
- **WHEN** se delega "hazme un informe"
- **THEN** llega un `ask`; tras el `answer`, la tarea vuelve a `working` y el `finish` `completed` refleja la respuesta en `result_text`

#### Scenario: Límite de preguntas
- **WHEN** el agente intenta una cuarta pregunta en la misma tarea
- **THEN** no se envía `ask` y el agente continúa hasta el `finish`

### Requirement: Vencimiento de preguntas
Una pregunta sin respuesta durante `ASK_TIMEOUT_S` (por defecto 1.800 s) SHALL marcarse `expired` y la tarea MUST terminar con `finish` fallido y `error.code: "timeout"`.

#### Scenario: Pregunta vencida
- **WHEN** pasa `ASK_TIMEOUT_S` sin `answer`
- **THEN** la pregunta queda `expired`, llega `finish` `failed` con `timeout` y el agente empieza la siguiente tarea de su cola

### Requirement: Tiempos y errores de ejecución
El trabajo del agente (sin contar la espera de respuestas) SHALL limitarse a `TASK_TIMEOUT_S` (por defecto 600 s). Cada situación MUST terminar en `finish` `failed` con: `timeout` si se supera el tiempo; `model_error` si el proveedor devuelve un error, con un mensaje sin datos sensibles; `internal_error` ante un error no previsto. En todos los casos la tarea MUST guardar `error`, `finished_at` y el consumo medido, y el agente MUST pasar a la siguiente tarea de su cola.

#### Scenario: CA11 · Tiempo máximo superado
- **WHEN** el trabajo del agente supera `TASK_TIMEOUT_S`
- **THEN** llega `finish` `failed` con `error.code: "timeout"` y la tarea queda `failed` con `finished_at`

#### Scenario: Error del proveedor
- **WHEN** el proveedor responde con un error (p. ej. API key inválida)
- **THEN** llega `finish` `failed` con `error.code: "model_error"` y el mensaje no contiene la key ni el cuerpo de la respuesta

### Requirement: Resultado de la tarea
Al terminar, `result_text` SHALL ser el último mensaje del agente y `usage` MUST sumar los tokens de entrada, salida y total de toda la tarea, incluidas las reanudaciones, con el `model_id`. `started_at` MUST ser la primera vez que la tarea pasó a `working` y `finished_at` el momento del estado final.

#### Scenario: Consumo con reanudación
- **WHEN** una tarea pregunta, se reanuda y termina
- **THEN** `usage` del `finish` suma el consumo de antes y después de la pregunta
