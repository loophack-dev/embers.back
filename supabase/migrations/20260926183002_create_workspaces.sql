-- Create the workspaces table and seed the fixed default workspace.
-- RLS is intentionally left disabled: only the backend accesses this database.

create extension if not exists pgcrypto;

create table if not exists public.workspaces (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    created_at timestamptz not null default now()
);

-- Fixed id for the single default workspace used by the demo.
-- Keep in sync with DEFAULT_WORKSPACE_ID in .env.example.
insert into public.workspaces (id, name)
values ('00000000-0000-0000-0000-000000000001', 'Oficina principal')
on conflict (id) do nothing;
