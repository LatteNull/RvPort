--liquibase formatted sql

--changeset rvport:0045-task-cancellation-fields
ALTER TABLE tasks
    ADD COLUMN cancel_requested_at timestamptz,
    ADD COLUMN cancel_requested_by uuid REFERENCES users(id),
    ADD COLUMN cancel_reason text;

CREATE INDEX tasks_cancel_requested_at_idx ON tasks (cancel_requested_at)
    WHERE cancel_requested_at IS NOT NULL;

--changeset rvport:0046-task-runtime-handles
CREATE TABLE task_runtime_handles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id uuid NOT NULL REFERENCES tasks(id),
    project_id uuid NOT NULL REFERENCES projects(id),
    worker_instance_id text NOT NULL,
    handle_type text NOT NULL,
    status text NOT NULL,
    local_pid bigint,
    remote_pid bigint,
    remote_pgid bigint,
    environment_id uuid REFERENCES environments(id),
    command_marker text,
    cancel_requested_at timestamptz,
    started_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    terminated_at timestamptz,
    error_code text,
    error_message text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT task_runtime_handles_type_chk CHECK (handle_type IN ('TASK', 'LOCAL_PROCESS', 'REMOTE_PROCESS')),
    CONSTRAINT task_runtime_handles_status_chk CHECK (status IN (
        'ACTIVE',
        'CANCEL_REQUESTED',
        'CANCELLING',
        'CANCELLED',
        'TERMINATED',
        'FAILED',
        'WORKER_LOST',
        'CANCEL_ROUTE_UNAVAILABLE',
        'CANCEL_UNKNOWN',
        'CANCEL_FAILED'
    )),
    CONSTRAINT task_runtime_handles_local_pid_chk CHECK (local_pid IS NULL OR local_pid > 0),
    CONSTRAINT task_runtime_handles_remote_pid_chk CHECK (remote_pid IS NULL OR remote_pid > 0),
    CONSTRAINT task_runtime_handles_remote_pgid_chk CHECK (remote_pgid IS NULL OR remote_pgid > 0)
);

CREATE INDEX task_runtime_handles_task_idx ON task_runtime_handles (task_id);
CREATE INDEX task_runtime_handles_project_idx ON task_runtime_handles (project_id);
CREATE INDEX task_runtime_handles_worker_idx ON task_runtime_handles (worker_instance_id);
CREATE INDEX task_runtime_handles_status_idx ON task_runtime_handles (status);
CREATE INDEX task_runtime_handles_updated_idx ON task_runtime_handles (updated_at);
CREATE UNIQUE INDEX task_runtime_handles_active_task_uidx
    ON task_runtime_handles (task_id)
    WHERE status IN ('ACTIVE', 'CANCEL_REQUESTED', 'CANCELLING');
