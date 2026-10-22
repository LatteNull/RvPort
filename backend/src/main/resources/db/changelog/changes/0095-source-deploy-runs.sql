--liquibase formatted sql

--changeset rvport:0095-source-deploy-runs
CREATE TABLE IF NOT EXISTS source_deploy_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    task_id uuid NOT NULL UNIQUE REFERENCES tasks(id) ON DELETE CASCADE,
    source_revision_id uuid NOT NULL REFERENCES source_revisions(id) ON DELETE CASCADE,
    environment_id uuid NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
    remote_path text NOT NULL,
    deploy_strategy varchar(32) NOT NULL DEFAULT 'TAR_OVER_SSH',
    force boolean NOT NULL DEFAULT false,
    status varchar(32) NOT NULL,
    file_count integer,
    total_bytes bigint,
    exit_code integer,
    summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    started_at timestamptz,
    finished_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE source_deploy_runs
    DROP CONSTRAINT IF EXISTS source_deploy_runs_strategy_chk;

ALTER TABLE source_deploy_runs
    ADD CONSTRAINT source_deploy_runs_strategy_chk
        CHECK (deploy_strategy IN ('TAR_OVER_SSH'));

ALTER TABLE source_deploy_runs
    DROP CONSTRAINT IF EXISTS source_deploy_runs_status_chk;

ALTER TABLE source_deploy_runs
    ADD CONSTRAINT source_deploy_runs_status_chk
        CHECK (status IN ('PENDING', 'QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'TIMEOUT'));

CREATE INDEX IF NOT EXISTS source_deploy_runs_project_created_at_idx
    ON source_deploy_runs(project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS source_deploy_runs_source_env_created_at_idx
    ON source_deploy_runs(source_revision_id, environment_id, created_at DESC);

CREATE INDEX IF NOT EXISTS source_deploy_runs_status_created_at_idx
    ON source_deploy_runs(status, created_at DESC);
