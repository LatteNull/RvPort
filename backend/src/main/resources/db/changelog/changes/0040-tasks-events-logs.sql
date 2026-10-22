--liquibase formatted sql

--changeset rvport:0040-tasks
CREATE TABLE tasks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id),
    type text NOT NULL,
    status text NOT NULL,
    progress integer,
    message text,
    input_snapshot jsonb NOT NULL,
    created_by uuid NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    queued_at timestamptz,
    started_at timestamptz,
    finished_at timestamptz,
    timeout_seconds integer,
    error_code text,
    error_message text,
    retry_count integer NOT NULL DEFAULT 0,
    CONSTRAINT tasks_status_chk CHECK (status IN ('PENDING', 'QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'TIMEOUT')),
    CONSTRAINT tasks_progress_chk CHECK (progress IS NULL OR progress BETWEEN 0 AND 100),
    CONSTRAINT tasks_retry_count_chk CHECK (retry_count >= 0),
    CONSTRAINT tasks_timeout_seconds_chk CHECK (timeout_seconds IS NULL OR timeout_seconds > 0)
);

CREATE INDEX tasks_project_created_idx ON tasks (project_id, created_at DESC);
CREATE INDEX tasks_status_idx ON tasks (status);
CREATE INDEX tasks_type_status_idx ON tasks (type, status);

ALTER TABLE source_imports
    ADD CONSTRAINT source_imports_task_fk FOREIGN KEY (task_id) REFERENCES tasks(id);

ALTER TABLE environment_snapshots
    ADD CONSTRAINT environment_snapshots_task_fk FOREIGN KEY (task_id) REFERENCES tasks(id);

--changeset rvport:0041-task-events
CREATE TABLE task_events (
    id bigserial PRIMARY KEY,
    event_id text NOT NULL,
    project_id uuid NOT NULL REFERENCES projects(id),
    task_id uuid NOT NULL REFERENCES tasks(id),
    event_type text NOT NULL,
    status text,
    progress integer,
    message text,
    log_level text,
    log_excerpt text,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT task_events_event_id_uidx UNIQUE (event_id),
    CONSTRAINT task_events_status_chk CHECK (status IS NULL OR status IN ('PENDING', 'QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'TIMEOUT')),
    CONSTRAINT task_events_progress_chk CHECK (progress IS NULL OR progress BETWEEN 0 AND 100),
    CONSTRAINT task_events_log_level_chk CHECK (log_level IS NULL OR log_level IN ('TRACE', 'DEBUG', 'INFO', 'WARN', 'ERROR'))
);

CREATE INDEX task_events_project_id_idx ON task_events (project_id, id);
CREATE INDEX task_events_task_id_idx ON task_events (task_id, id);
CREATE INDEX task_events_occurred_at_idx ON task_events (occurred_at);

--changeset rvport:0042-task-logs
CREATE TABLE task_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id uuid NOT NULL REFERENCES tasks(id),
    project_id uuid NOT NULL REFERENCES projects(id),
    log_type text NOT NULL,
    file_path text NOT NULL,
    size_bytes bigint,
    sha256 text,
    excerpt text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT task_logs_type_chk CHECK (log_type IN ('STDOUT', 'STDERR', 'COMBINED', 'TOOL')),
    CONSTRAINT task_logs_size_bytes_chk CHECK (size_bytes IS NULL OR size_bytes >= 0)
);

CREATE INDEX task_logs_task_idx ON task_logs (task_id);
CREATE INDEX task_logs_project_created_idx ON task_logs (project_id, created_at DESC);

--changeset rvport:0043-tool-runs
CREATE TABLE tool_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id uuid NOT NULL REFERENCES tasks(id),
    project_id uuid NOT NULL REFERENCES projects(id),
    tool_name text NOT NULL,
    tool_version text,
    command_summary text,
    exit_code integer,
    status text NOT NULL,
    summary jsonb,
    started_at timestamptz,
    finished_at timestamptz,
    CONSTRAINT tool_runs_status_chk CHECK (status IN ('PENDING', 'QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'TIMEOUT'))
);

CREATE INDEX tool_runs_task_idx ON tool_runs (task_id);
CREATE INDEX tool_runs_project_started_idx ON tool_runs (project_id, started_at DESC);
CREATE INDEX tool_runs_tool_name_idx ON tool_runs (tool_name);
