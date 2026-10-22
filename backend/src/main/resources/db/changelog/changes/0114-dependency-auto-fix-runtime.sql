--liquibase formatted sql

--changeset rvport:0114-dependency-auto-fix-runtime-tables
CREATE TABLE IF NOT EXISTS dependency_auto_fix_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    task_id uuid NOT NULL UNIQUE REFERENCES tasks(id),
    dependency_analysis_run_id uuid NOT NULL REFERENCES dependency_analysis_runs(id) ON DELETE CASCADE,
    source_revision_id uuid NOT NULL REFERENCES source_revisions(id) ON DELETE CASCADE,
    target_environment_id uuid NOT NULL REFERENCES environments(id),
    environment_config_version bigint NOT NULL,
    rerun_dependency_analysis_run_id uuid REFERENCES dependency_analysis_runs(id),
    rerun_dependency_analysis_task_id uuid REFERENCES tasks(id),
    status text NOT NULL,
    selected_count integer NOT NULL DEFAULT 0,
    succeeded_count integer NOT NULL DEFAULT 0,
    failed_count integer NOT NULL DEFAULT 0,
    skipped_count integer NOT NULL DEFAULT 0,
    summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_summary text,
    started_at timestamptz,
    finished_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT dependency_auto_fix_runs_status_chk CHECK (status IN (
        'PENDING',
        'RUNNING',
        'SUCCEEDED',
        'PARTIALLY_SUCCEEDED',
        'FAILED',
        'CANCELLED',
        'TIMEOUT',
        'SUCCEEDED_WITH_REANALYSIS_FAILED'
    ))
);

CREATE INDEX IF NOT EXISTS dependency_auto_fix_runs_project_created_idx
    ON dependency_auto_fix_runs(project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS dependency_auto_fix_runs_project_revision_created_idx
    ON dependency_auto_fix_runs(project_id, source_revision_id, environment_config_version, created_at DESC);

CREATE INDEX IF NOT EXISTS dependency_auto_fix_runs_analysis_idx
    ON dependency_auto_fix_runs(dependency_analysis_run_id);

CREATE TABLE IF NOT EXISTS dependency_auto_fix_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dependency_auto_fix_run_id uuid NOT NULL REFERENCES dependency_auto_fix_runs(id) ON DELETE CASCADE,
    dependency_result_item_id uuid NOT NULL REFERENCES dependency_analysis_result_items(id) ON DELETE CASCADE,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    source_revision_id uuid NOT NULL REFERENCES source_revisions(id) ON DELETE CASCADE,
    risk_level text NOT NULL,
    target_match_status text NOT NULL,
    source_provider_package text,
    source_provider_version text,
    target_provider_package text,
    target_provider_version text,
    install_package_name text NOT NULL,
    install_version_constraint text,
    default_selected boolean NOT NULL DEFAULT false,
    status text NOT NULL,
    exit_code integer,
    error_summary text,
    evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    started_at timestamptz,
    finished_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT dependency_auto_fix_items_status_chk CHECK (status IN (
        'PENDING',
        'RUNNING',
        'SUCCEEDED',
        'FAILED',
        'CANCELLED',
        'SKIPPED_ALREADY_SATISFIED',
        'SKIPPED_UNAVAILABLE'
    )),
    CONSTRAINT dependency_auto_fix_items_risk_level_chk CHECK (risk_level IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO', 'COMMENT'))
);

CREATE INDEX IF NOT EXISTS dependency_auto_fix_items_run_created_idx
    ON dependency_auto_fix_items(dependency_auto_fix_run_id, created_at DESC);

CREATE INDEX IF NOT EXISTS dependency_auto_fix_items_project_revision_status_idx
    ON dependency_auto_fix_items(project_id, source_revision_id, status);

CREATE INDEX IF NOT EXISTS dependency_auto_fix_items_project_revision_package_idx
    ON dependency_auto_fix_items(project_id, source_revision_id, install_package_name);

CREATE INDEX IF NOT EXISTS dependency_auto_fix_items_result_item_idx
    ON dependency_auto_fix_items(dependency_result_item_id);

--changeset rvport:0115-dependency-auto-fix-task-type
ALTER TABLE tasks
    DROP CONSTRAINT IF EXISTS tasks_type_chk;

ALTER TABLE tasks
    ADD CONSTRAINT tasks_type_chk CHECK (type IN (
        'SOURCE_GIT_SYNC',
        'SOURCE_DEPLOY',
        'ENV_TEST_CONNECTION',
        'ENV_COLLECT',
        'ENV_RUN_SCRIPT',
        'DEPENDENCY_ANALYSIS',
        'DEPENDENCY_AUTO_FIX',
        'KB_SCAN',
        'REPORT_GENERATE',
        'REPORT_COMPARE',
        'RECHECK_DIFF',
        'BUILD_VALIDATION',
        'AUTOMATED_TEST',
        'TEST_LOG_COMPARE',
        'ARCHIVE_PROJECT'
    ));
