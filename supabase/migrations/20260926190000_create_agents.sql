-- Agents of the office. Null rule (phase 1): instructions and tools accept null;
-- the API converts them to "" and [] respectively.

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create table public.agents (
    id uuid primary key default gen_random_uuid(),
    workspace_id uuid not null
        default '00000000-0000-0000-0000-000000000001'
        references public.workspaces (id) on delete cascade,
    name text not null,
    model_config jsonb not null,
    identity jsonb not null,
    instructions text,
    tools text[],
    status text not null default 'active',
    version integer not null default 1,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint agents_name_length check (char_length(name) between 1 and 60),
    constraint agents_instructions_length check (
        instructions is null or char_length(instructions) <= 8000
    ),
    constraint agents_status_valid check (status in ('active', 'archived')),
    constraint agents_model_config_shape check (
        jsonb_typeof(model_config) = 'object'
        and model_config ? 'provider'
        and model_config ? 'model_id'
    ),
    constraint agents_identity_shape check (
        jsonb_typeof(identity) = 'object' and identity ? 'role'
    ),
    constraint agents_version_positive check (version >= 1)
);

create unique index agents_active_name_unique
    on public.agents (workspace_id, name)
    where status = 'active';

create index agents_workspace_created_idx
    on public.agents (workspace_id, created_at);

create trigger agents_set_updated_at
    before update on public.agents
    for each row execute function public.set_updated_at();
