-- Tasks delegated to agents and questions the agent asks the person (phase 2).
-- Null rule: minimal fields are not null; everything else accepts null.

create table public.tasks (
    id uuid primary key default gen_random_uuid(),
    workspace_id uuid not null
        default '00000000-0000-0000-0000-000000000001'
        references public.workspaces (id) on delete cascade,
    agent_id uuid not null references public.agents (id) on delete restrict,
    instruction text not null,
    status text not null default 'queued',
    agent_snapshot jsonb not null,
    created_at timestamptz not null default now(),
    parent_task_id uuid references public.tasks (id),
    expected_output text,
    result_text text,
    error jsonb,
    usage jsonb,
    started_at timestamptz,
    finished_at timestamptz,
    constraint tasks_instruction_length check (char_length(instruction) between 1 and 4000),
    constraint tasks_status_valid check (
        status in ('queued', 'working', 'waiting_user', 'completed', 'failed', 'canceled')
    ),
    constraint tasks_expected_output_valid check (
        expected_output is null or expected_output in ('docx', 'pptx', 'md')
    ),
    constraint tasks_agent_snapshot_object check (jsonb_typeof(agent_snapshot) = 'object'),
    constraint tasks_error_object check (error is null or jsonb_typeof(error) = 'object'),
    constraint tasks_usage_object check (usage is null or jsonb_typeof(usage) = 'object')
);

create index tasks_agent_status_idx on public.tasks (agent_id, status);
create index tasks_workspace_created_idx on public.tasks (workspace_id, created_at);

create table public.task_questions (
    id uuid primary key default gen_random_uuid(),
    workspace_id uuid not null
        default '00000000-0000-0000-0000-000000000001'
        references public.workspaces (id) on delete cascade,
    task_id uuid not null references public.tasks (id) on delete cascade,
    question text not null,
    status text not null default 'pending',
    asked_at timestamptz not null default now(),
    options jsonb,
    answer text,
    interrupt_id text,
    answered_at timestamptz,
    constraint task_questions_question_length check (char_length(question) between 1 and 1000),
    constraint task_questions_status_valid check (status in ('pending', 'answered', 'expired')),
    constraint task_questions_options_shape check (
        options is null
        or (jsonb_typeof(options) = 'array' and jsonb_array_length(options) <= 6)
    ),
    constraint task_questions_answer_length check (
        answer is null or char_length(answer) between 1 and 2000
    )
);

-- At most one pending question per task.
create unique index task_questions_one_pending_per_task
    on public.task_questions (task_id)
    where status = 'pending';

create index task_questions_status_asked_idx on public.task_questions (status, asked_at);
