--liquibase formatted sql

--changeset rvport:0080-build-runs
CREATE TABLE build_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id),
    task_id uuid NOT NULL UNIQUE REFERENCES tasks(id),
    source_revision_id uuid NOT NULL REFERENCES source_revisions(id),
    environment_id uuid NOT NULL REFERENCES environments(id),
    command text NOT NULL,
    working_directory text,
    timeout_seconds integer,
    exit_code integer,
    status text NOT NULL,
    failure_category text,
    stdout_log_id uuid REFERENCES task_logs(id),
    stderr_log_id uuid REFERENCES task_logs(id),
    started_at timestamptz,
    finished_at timestamptz,
    CONSTRAINT build_runs_timeout_seconds_chk CHECK (timeout_seconds IS NULL OR timeout_seconds > 0),
    CONSTRAINT build_runs_status_chk CHECK (status IN ('PENDING', 'QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'TIMEOUT'))
);

CREATE INDEX build_runs_project_started_idx ON build_runs (project_id, started_at DESC);
CREATE INDEX build_runs_source_revision_idx ON build_runs (source_revision_id);
CREATE INDEX build_runs_environment_idx ON build_runs (environment_id);

--changeset rvport:0081-test-runs
CREATE TABLE test_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id),
    task_id uuid NOT NULL UNIQUE REFERENCES tasks(id),
    build_run_id uuid REFERENCES build_runs(id),
    source_revision_id uuid NOT NULL REFERENCES source_revisions(id),
    environment_id uuid NOT NULL REFERENCES environments(id),
    command text NOT NULL,
    working_directory text,
    timeout_seconds integer,
    exit_code integer,
    passed_count integer,
    failed_count integer,
    skipped_count integer,
    status text NOT NULL,
    stdout_log_id uuid REFERENCES task_logs(id),
    stderr_log_id uuid REFERENCES task_logs(id),
    started_at timestamptz,
    finished_at timestamptz,
    CONSTRAINT test_runs_timeout_seconds_chk CHECK (timeout_seconds IS NULL OR timeout_seconds > 0),
    CONSTRAINT test_runs_passed_count_chk CHECK (passed_count IS NULL OR passed_count >= 0),
    CONSTRAINT test_runs_failed_count_chk CHECK (failed_count IS NULL OR failed_count >= 0),
    CONSTRAINT test_runs_skipped_count_chk CHECK (skipped_count IS NULL OR skipped_count >= 0),
    CONSTRAINT test_runs_status_chk CHECK (status IN ('PENDING', 'QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'TIMEOUT'))
);

CREATE INDEX test_runs_project_started_idx ON test_runs (project_id, started_at DESC);
CREATE INDEX test_runs_build_run_idx ON test_runs (build_run_id);
CREATE INDEX test_runs_environment_idx ON test_runs (environment_id);

--changeset rvport:0082-archives
CREATE TABLE archives (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id),
    task_id uuid REFERENCES tasks(id),
    name text NOT NULL,
    status text NOT NULL,
    summary jsonb,
    archive_path text,
    size_bytes bigint,
    sha256 text,
    created_by uuid NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT archives_status_chk CHECK (status IN ('PENDING', 'QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'TIMEOUT')),
    CONSTRAINT archives_size_bytes_chk CHECK (size_bytes IS NULL OR size_bytes >= 0)
);

CREATE INDEX archives_project_created_idx ON archives (project_id, created_at DESC);
CREATE INDEX archives_task_idx ON archives (task_id);

--changeset rvport:0083-archive-items
CREATE TABLE archive_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    archive_id uuid NOT NULL REFERENCES archives(id),
    item_type text NOT NULL,
    item_id uuid,
    file_path text,
    metadata jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX archive_items_archive_idx ON archive_items (archive_id);
CREATE INDEX archive_items_type_item_idx ON archive_items (item_type, item_id);

--changeset rvport:0084-audit-logs
CREATE TABLE audit_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid REFERENCES projects(id),
    user_id uuid REFERENCES users(id),
    action text NOT NULL,
    resource_type text NOT NULL,
    resource_id uuid,
    ip_address inet,
    user_agent text,
    request_id text,
    details jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX audit_logs_project_created_idx ON audit_logs (project_id, created_at DESC);
CREATE INDEX audit_logs_user_created_idx ON audit_logs (user_id, created_at DESC);
CREATE INDEX audit_logs_resource_idx ON audit_logs (resource_type, resource_id);
CREATE INDEX audit_logs_action_created_idx ON audit_logs (action, created_at DESC);
