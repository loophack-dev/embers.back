-- Visual settings defined by the front end, stored as-is.
-- owner_id has no foreign key because it points to an agent or a workspace.

create table public.ui_settings (
    id uuid primary key default gen_random_uuid(),
    workspace_id uuid not null
        default '00000000-0000-0000-0000-000000000001'
        references public.workspaces (id) on delete cascade,
    owner_type text not null,
    owner_id uuid not null,
    namespace text not null,
    data jsonb,
    updated_at timestamptz not null default now(),
    constraint ui_settings_owner_type_valid check (owner_type in ('workspace', 'agent')),
    constraint ui_settings_data_object check (data is null or jsonb_typeof(data) = 'object'),
    constraint ui_settings_data_size check (data is null or octet_length(data::text) <= 65536),
    constraint ui_settings_owner_namespace_unique
        unique (workspace_id, owner_type, owner_id, namespace)
);

create trigger ui_settings_set_updated_at
    before update on public.ui_settings
    for each row execute function public.set_updated_at();
