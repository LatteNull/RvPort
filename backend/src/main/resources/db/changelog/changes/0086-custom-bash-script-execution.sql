-- liquibase formatted sql

-- changeset rvport:0086-task-script-payloads
create table task_script_payloads (
    id uuid primary key default gen_random_uuid(),
    project_id uuid not null references projects(id) on delete cascade,
    task_id uuid not null references tasks(id) on delete cascade,
    script_sha256 varchar(64) not null,
    script_length integer not null,
    encrypted_payload jsonb not null,
    key_id varchar(120) not null,
    created_by uuid references users(id) on delete set null,
    created_at timestamptz not null default now(),
    constraint uq_task_script_payloads_task unique (task_id),
    constraint ck_task_script_payloads_sha256 check (script_sha256 ~ '^[0-9a-f]{64}$'),
    constraint ck_task_script_payloads_length check (script_length > 0 and script_length <= 12000)
);

create index idx_task_script_payloads_project_created
    on task_script_payloads (project_id, created_at desc, id desc);

-- changeset rvport:0086-task-log-events
create table task_log_events (
    id bigserial primary key,
    project_id uuid not null references projects(id) on delete cascade,
    task_id uuid not null references tasks(id) on delete cascade,
    log_type varchar(32) not null,
    sequence bigint not null,
    content text not null,
    created_at timestamptz not null default now(),
    constraint ck_task_log_events_log_type check (log_type in ('STDOUT', 'STDERR')),
    constraint ck_task_log_events_sequence check (sequence > 0),
    constraint ck_task_log_events_content check (char_length(content) > 0 and char_length(content) <= 4000),
    constraint uq_task_log_events_task_sequence unique (task_id, sequence)
);

create index idx_task_log_events_task_id
    on task_log_events (task_id, id);

create index idx_task_log_events_project_task_id
    on task_log_events (project_id, task_id, id);

create index idx_task_log_events_task_sequence
    on task_log_events (task_id, sequence);
