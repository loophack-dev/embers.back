-- Every WebSocket message (direction in/out) and every internal event (direction null).

create table public.task_events (
    id bigint generated always as identity primary key,
    workspace_id uuid not null
        default '00000000-0000-0000-0000-000000000001'
        references public.workspaces (id) on delete cascade,
    type text not null,
    created_at timestamptz not null default now(),
    task_id uuid references public.tasks (id) on delete cascade,
    agent_id uuid references public.agents (id) on delete cascade,
    direction text,
    data jsonb,
    constraint task_events_direction_valid check (direction is null or direction in ('in', 'out'))
);

create index task_events_workspace_id_idx on public.task_events (workspace_id, id);
create index task_events_task_idx on public.task_events (task_id);
