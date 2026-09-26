# app-config Specification

## Purpose
Define cómo se configura y arranca el backend de Embers: variables de entorno, conexión a Postgres de Supabase con su ciclo de vida, CORS y logs estructurados.

## Requirements

### Requirement: Configuración por variables de entorno
El sistema SHALL leer su configuración de variables de entorno (y de un archivo `.env` opcional). `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL` y `DEFAULT_WORKSPACE_ID` MUST ser obligatorias; `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY` y `CORS_ORIGINS` MUST ser opcionales. El repositorio MUST incluir un `.env.example` con todas ellas y sin valores secretos reales.

#### Scenario: Falta una variable obligatoria
- **WHEN** la app arranca sin `DATABASE_URL`
- **THEN** el arranque falla con un error que nombra la variable faltante

#### Scenario: Variables opcionales ausentes
- **WHEN** la app arranca sin ninguna API key de proveedor ni `CORS_ORIGINS`
- **THEN** la app arranca normalmente

#### Scenario: DEFAULT_WORKSPACE_ID inválido
- **WHEN** `DEFAULT_WORKSPACE_ID` no es un UUID
- **THEN** el arranque falla con un error de configuración

### Requirement: Ciclo de vida de la conexión a la base
El sistema SHALL abrir el pool de conexiones a Postgres al arrancar y cerrarlo al apagarse. La app MUST arrancar aunque la base no esté disponible en ese momento.

#### Scenario: Arranque con la base caída
- **WHEN** la app arranca y Postgres no responde
- **THEN** la app queda escuchando peticiones y `GET /health` responde `degraded`

#### Scenario: Apagado
- **WHEN** la app se detiene
- **THEN** el pool de conexiones se cierra

### Requirement: CORS configurable
El sistema SHALL permitir peticiones de origen cruzado desde cualquier origen por defecto. `CORS_ORIGINS` MUST aceptar `*` (valor por defecto, también cuando está vacía o ausente) para permitir cualquier origen, o una lista separada por comas para restringirlos.

#### Scenario: Cualquier origen por defecto
- **WHEN** `CORS_ORIGINS` no está definida o vale `*` y llega una petición preflight desde cualquier origen
- **THEN** la respuesta incluye `Access-Control-Allow-Origin: *`

#### Scenario: Origen no permitido
- **WHEN** `CORS_ORIGINS=http://localhost:5173` y llega una petición desde otro origen
- **THEN** la respuesta no incluye `Access-Control-Allow-Origin`

#### Scenario: Origen permitido
- **WHEN** `CORS_ORIGINS=http://localhost:5173` y llega una petición preflight desde `http://localhost:5173`
- **THEN** la respuesta incluye `Access-Control-Allow-Origin: http://localhost:5173`

### Requirement: Logs estructurados sin secretos
El sistema SHALL escribir sus logs como una línea JSON por registro, con al menos `ts`, `level`, `logger` y `message`. Ningún registro MUST contener el valor de `SUPABASE_SERVICE_ROLE_KEY` ni de las API keys de proveedores.

#### Scenario: Formato del log
- **WHEN** la app escribe un registro de log
- **THEN** la línea es un objeto JSON válido con `ts`, `level`, `logger` y `message`

#### Scenario: Secretos fuera del log
- **WHEN** la app arranca con API keys configuradas y registra su configuración
- **THEN** ningún registro contiene el valor de esas keys
