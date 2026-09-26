# Spec Delta

## Purpose

Garantiza que exista una única oficina por defecto, con id fijo, a la que pertenecen todos los datos del demo.

## ADDED Requirements

### Requirement: Tabla de oficinas
Las migraciones SHALL crear la tabla `workspaces` con `id` (uuid, PK, por defecto `gen_random_uuid()`), `name` (text, no nulo) y `created_at` (timestamptz, no nulo, por defecto `now()`).

#### Scenario: Migraciones sobre base vacía
- **WHEN** se aplican las migraciones sobre un Supabase vacío, local o remoto
- **THEN** terminan sin errores y la tabla `workspaces` existe con esas columnas

### Requirement: Oficina por defecto
Las migraciones SHALL insertar la oficina por defecto con el id fijo `00000000-0000-0000-0000-000000000001` y el nombre "Oficina principal". La inserción MUST ser idempotente. El valor por defecto de `DEFAULT_WORKSPACE_ID` en `.env.example` MUST coincidir con ese id.

#### Scenario: La oficina existe tras migrar
- **WHEN** se aplican las migraciones
- **THEN** existe exactamente una fila en `workspaces` con id `00000000-0000-0000-0000-000000000001` y nombre "Oficina principal"

#### Scenario: Reaplicar no duplica
- **WHEN** la sentencia de inserción se ejecuta de nuevo
- **THEN** sigue existiendo una sola oficina por defecto
