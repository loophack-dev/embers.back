-- Character state of each agent, kept by the database from its tasks and published to Realtime
-- so the front end can animate the office. Only the database writes this column.

alter table public.agents
    add column character_status text not null default 'idle',
    add constraint agents_character_status_valid
        check (character_status in ('idle', 'working', 'waiting'));

create or replace function public.refresh_agent_character_status(target_agent_id uuid)
returns void
language plpgsql
as $$
declare
    next_status text;
begin
    select case
        when bool_or(status = 'working') then 'working'
        when bool_or(status = 'waiting_user') then 'waiting'
        else 'idle'
    end
    into next_status
    from public.tasks
    where agent_id = target_agent_id and status in ('working', 'waiting_user');

    update public.agents
    set character_status = coalesce(next_status, 'idle')
    where id = target_agent_id
      and character_status is distinct from coalesce(next_status, 'idle');
end;
$$;

create or replace function public.tasks_refresh_character_status()
returns trigger
language plpgsql
as $$
begin
    if tg_op in ('INSERT', 'UPDATE') then
        perform public.refresh_agent_character_status(new.agent_id);
    end if;
    if tg_op in ('UPDATE', 'DELETE') and (tg_op = 'DELETE' or old.agent_id <> new.agent_id) then
        perform public.refresh_agent_character_status(old.agent_id);
    end if;
    return null;
end;
$$;

create trigger tasks_refresh_character_status
    after insert or update of status, agent_id or delete on public.tasks
    for each row execute function public.tasks_refresh_character_status();

-- updated_at reflects configuration changes only, not the character state.
create or replace function public.agents_set_updated_at()
returns trigger
language plpgsql
as $$
begin
    if (to_jsonb(new) - 'character_status' - 'updated_at')
        is distinct from (to_jsonb(old) - 'character_status' - 'updated_at') then
        new.updated_at = now();
    end if;
    return new;
end;
$$;

drop trigger agents_set_updated_at on public.agents;
create trigger agents_set_updated_at
    before update on public.agents
    for each row execute function public.agents_set_updated_at();

-- Backfill agents that already have open tasks.
select public.refresh_agent_character_status(id) from public.agents;

do $$
begin
    if not exists (
        select 1 from pg_publication_tables
        where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'agents'
    ) then
        alter publication supabase_realtime add table public.agents;
    end if;
end;
$$;
