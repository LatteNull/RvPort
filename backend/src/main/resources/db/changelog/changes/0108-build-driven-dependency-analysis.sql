--liquibase formatted sql

--changeset rvport:0108-build-driven-dependency-analysis-build-scope
ALTER TABLE build_runs
    ADD COLUMN IF NOT EXISTS build_scope text NOT NULL DEFAULT 'BOTH',
    ADD COLUMN IF NOT EXISTS build_facts jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE build_runs
    DROP CONSTRAINT IF EXISTS build_runs_build_scope_chk;

ALTER TABLE build_runs
    ADD CONSTRAINT build_runs_build_scope_chk CHECK (build_scope IN ('BOTH', 'SOURCE_ONLY'));

CREATE INDEX IF NOT EXISTS build_runs_project_revision_scope_status_idx
    ON build_runs(project_id, source_revision_id, build_scope, status, created_at DESC);

--changeset rvport:0109-dependency-analysis-tables
CREATE TABLE IF NOT EXISTS dependency_analysis_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    task_id uuid NOT NULL UNIQUE REFERENCES tasks(id),
    source_revision_id uuid NOT NULL REFERENCES source_revisions(id) ON DELETE CASCADE,
    source_build_run_id uuid NOT NULL REFERENCES build_runs(id),
    target_environment_id uuid NOT NULL REFERENCES environments(id),
    environment_config_version bigint NOT NULL,
    status text NOT NULL,
    summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    warnings jsonb NOT NULL DEFAULT '[]'::jsonb,
    started_at timestamptz,
    finished_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT dependency_analysis_runs_status_chk CHECK (status IN ('PENDING', 'QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'TIMEOUT'))
);

CREATE INDEX IF NOT EXISTS dependency_analysis_runs_project_created_idx
    ON dependency_analysis_runs(project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS dependency_analysis_runs_project_revision_status_idx
    ON dependency_analysis_runs(project_id, source_revision_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS dependency_analysis_runs_task_idx
    ON dependency_analysis_runs(task_id);

CREATE INDEX IF NOT EXISTS dependency_analysis_runs_source_build_idx
    ON dependency_analysis_runs(source_build_run_id);

CREATE TABLE IF NOT EXISTS dependency_analysis_result_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    source_revision_id uuid NOT NULL REFERENCES source_revisions(id) ON DELETE CASCADE,
    task_id uuid NOT NULL REFERENCES tasks(id),
    dependency_analysis_run_id uuid NOT NULL REFERENCES dependency_analysis_runs(id) ON DELETE CASCADE,
    dependency_type text NOT NULL,
    dependency_name text NOT NULL,
    dependency_version text,
    target_match_status text NOT NULL,
    risk_level text NOT NULL,
    location_label text,
    recommendation text,
    confidence text,
    evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT dependency_analysis_result_items_type_chk CHECK (dependency_type IN (
        'BUILD_TOOL',
        'BUILD_PACKAGE',
        'LINK_LIBRARY',
        'RUNTIME_LIBRARY',
        'TEST_TOOL',
        'TEST_PACKAGE'
    )),
    CONSTRAINT dependency_analysis_result_items_match_status_chk CHECK (target_match_status IN (
        'TARGET_INSTALLED',
        'REPO_AVAILABLE',
        'PROVIDES_MATCH',
        'VERSION_MISMATCH',
        'SOURCE_BUILD_REQUIRED',
        'MISSING',
        'MANUAL_CONFIRM_REQUIRED'
    )),
    CONSTRAINT dependency_analysis_result_items_risk_level_chk CHECK (risk_level IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO', 'COMMENT')),
    CONSTRAINT dependency_analysis_result_items_confidence_chk CHECK (confidence IS NULL OR confidence IN ('HIGH', 'MEDIUM', 'LOW', 'OBSERVED'))
);

CREATE INDEX IF NOT EXISTS dependency_analysis_items_run_created_idx
    ON dependency_analysis_result_items(dependency_analysis_run_id, created_at DESC);

CREATE INDEX IF NOT EXISTS dependency_analysis_items_project_revision_created_idx
    ON dependency_analysis_result_items(project_id, source_revision_id, created_at DESC);

CREATE INDEX IF NOT EXISTS dependency_analysis_items_project_revision_type_idx
    ON dependency_analysis_result_items(project_id, source_revision_id, dependency_type);

CREATE INDEX IF NOT EXISTS dependency_analysis_items_project_revision_status_idx
    ON dependency_analysis_result_items(project_id, source_revision_id, target_match_status);

CREATE INDEX IF NOT EXISTS dependency_analysis_items_project_revision_risk_idx
    ON dependency_analysis_result_items(project_id, source_revision_id, risk_level);

CREATE INDEX IF NOT EXISTS dependency_analysis_items_project_revision_name_idx
    ON dependency_analysis_result_items(project_id, source_revision_id, dependency_name);

--changeset rvport:0110-dependency-analysis-enums
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
        'KB_SCAN',
        'REPORT_GENERATE',
        'RECHECK_DIFF',
        'BUILD_VALIDATION',
        'AUTOMATED_TEST',
        'TEST_LOG_COMPARE',
        'ARCHIVE_PROJECT'
    ));

ALTER TABLE migration_input_refs
    DROP CONSTRAINT IF EXISTS migration_input_refs_source_type_chk;

ALTER TABLE migration_input_refs
    ADD CONSTRAINT migration_input_refs_source_type_chk CHECK (source_type IN ('KB_FINDING', 'DEPENDENCY_RESULT'));

ALTER TABLE stored_artifacts
    DROP CONSTRAINT IF EXISTS stored_artifacts_owner_type_chk;

ALTER TABLE stored_artifacts
    ADD CONSTRAINT stored_artifacts_owner_type_chk CHECK (owner_type IN (
        'KB_SCAN',
        'DEPENDENCY_ANALYSIS',
        'MIGRATION_REPORT',
        'ARCHIVE',
        'AUTOMATED_TEST',
        'TEST_COMPARISON'
    ));
