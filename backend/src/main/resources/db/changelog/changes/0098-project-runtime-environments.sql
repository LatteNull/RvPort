--liquibase formatted sql

--changeset rvport:0098-project-runtime-environments
CREATE TABLE IF NOT EXISTS project_runtime_environments (
    project_id uuid PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    source_environment_id uuid REFERENCES environments(id),
    target_environment_id uuid REFERENCES environments(id),
    version bigint NOT NULL DEFAULT 1,
    updated_by uuid REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT project_runtime_environments_distinct_chk
        CHECK (
            source_environment_id IS NULL
            OR target_environment_id IS NULL
            OR source_environment_id <> target_environment_id
        )
);

CREATE INDEX IF NOT EXISTS project_runtime_environments_source_idx
    ON project_runtime_environments(source_environment_id);

CREATE INDEX IF NOT EXISTS project_runtime_environments_target_idx
    ON project_runtime_environments(target_environment_id);


ALTER TABLE source_deploy_runs
    ADD COLUMN IF NOT EXISTS environment_config_version bigint;

ALTER TABLE build_runs
    ADD COLUMN IF NOT EXISTS environment_config_version bigint;

ALTER TABLE test_runs
    ADD COLUMN IF NOT EXISTS environment_config_version bigint;


CREATE INDEX IF NOT EXISTS source_deploy_runs_project_env_config_idx
    ON source_deploy_runs(project_id, environment_config_version, created_at DESC);

CREATE INDEX IF NOT EXISTS source_deploy_runs_revision_env_config_idx
    ON source_deploy_runs(source_revision_id, environment_config_version, environment_id, created_at DESC);

CREATE INDEX IF NOT EXISTS build_runs_project_env_config_idx
    ON build_runs(project_id, environment_config_version, created_at DESC);

CREATE INDEX IF NOT EXISTS build_runs_revision_env_config_idx
    ON build_runs(source_revision_id, environment_config_version, environment_id, created_at DESC);

CREATE INDEX IF NOT EXISTS test_runs_project_env_config_idx
    ON test_runs(project_id, environment_config_version, started_at DESC);
