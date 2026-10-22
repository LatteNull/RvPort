-- liquibase formatted sql

-- changeset rvport:0091-task-secret-payloads
create table task_secret_payloads (
    id uuid primary key default gen_random_uuid(),
    project_id uuid not null references projects(id) on delete cascade,
    task_id uuid not null references tasks(id) on delete cascade,
    secret_type varchar(80) not null,
    secret_sha256 varchar(64) not null,
    encrypted_payload jsonb not null,
    key_id varchar(120) not null,
    created_by uuid references users(id) on delete set null,
    created_at timestamptz not null default now(),
    constraint uq_task_secret_payloads_task_type unique (task_id, secret_type),
    constraint ck_task_secret_payloads_type check (secret_type in ('SSH_PRECHECK_CREDENTIAL')),
    constraint ck_task_secret_payloads_sha256 check (secret_sha256 ~ '^[0-9a-f]{64}$')
);

create index idx_task_secret_payloads_project_created
    on task_secret_payloads (project_id, created_at desc, id desc);
