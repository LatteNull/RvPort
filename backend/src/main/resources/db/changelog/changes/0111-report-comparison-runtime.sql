--liquibase formatted sql

--changeset rvport:0111-report-comparison-runs
CREATE TABLE IF NOT EXISTS report_comparison_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    task_id uuid UNIQUE REFERENCES tasks(id),
    base_report_id uuid NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    target_report_id uuid NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    status text NOT NULL,
    summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_code text,
    error_message text,
    started_at timestamptz,
    finished_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT report_comparison_runs_status_chk CHECK (status IN ('PENDING', 'QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'TIMEOUT'))
);

CREATE UNIQUE INDEX IF NOT EXISTS report_comparison_runs_project_base_target_active_uidx
    ON report_comparison_runs(project_id, base_report_id, target_report_id)
    WHERE status IN ('PENDING', 'QUEUED', 'RUNNING', 'SUCCEEDED');

CREATE INDEX IF NOT EXISTS report_comparison_runs_project_created_idx
    ON report_comparison_runs(project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS report_comparison_runs_project_target_idx
    ON report_comparison_runs(project_id, target_report_id, created_at DESC);

CREATE INDEX IF NOT EXISTS report_comparison_runs_task_idx
    ON report_comparison_runs(task_id);

--changeset rvport:0112-report-comparison-diff-items
CREATE TABLE IF NOT EXISTS report_comparison_diff_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    comparison_run_id uuid NOT NULL REFERENCES report_comparison_runs(id) ON DELETE CASCADE,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    source_type text NOT NULL,
    old_source_id uuid,
    new_source_id uuid,
    diff_status text NOT NULL,
    severity text,
    title text,
    location_label text,
    recommendation text,
    confirmation_status text,
    fingerprint text,
    match_confidence text,
    match_reason text,
    old_snapshot jsonb,
    new_snapshot jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT report_comparison_diff_items_status_chk CHECK (diff_status IN ('NEW', 'RESOLVED', 'UNCHANGED', 'CHANGED')),
    CONSTRAINT report_comparison_diff_items_match_confidence_chk CHECK (match_confidence IS NULL OR match_confidence IN ('HIGH', 'MEDIUM', 'LOW'))
);

CREATE INDEX IF NOT EXISTS report_comparison_diff_items_run_idx
    ON report_comparison_diff_items(comparison_run_id);

CREATE INDEX IF NOT EXISTS report_comparison_diff_items_project_status_idx
    ON report_comparison_diff_items(project_id, comparison_run_id, diff_status);

CREATE INDEX IF NOT EXISTS report_comparison_diff_items_project_source_type_idx
    ON report_comparison_diff_items(project_id, comparison_run_id, source_type);

CREATE INDEX IF NOT EXISTS report_comparison_diff_items_project_severity_idx
    ON report_comparison_diff_items(project_id, comparison_run_id, severity);

CREATE INDEX IF NOT EXISTS report_comparison_diff_items_project_confidence_idx
    ON report_comparison_diff_items(project_id, comparison_run_id, match_confidence);

CREATE INDEX IF NOT EXISTS report_comparison_diff_items_fingerprint_idx
    ON report_comparison_diff_items(fingerprint);

--changeset rvport:0113-report-compare-task-type
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
        'REPORT_COMPARE',
        'RECHECK_DIFF',
        'BUILD_VALIDATION',
        'AUTOMATED_TEST',
        'TEST_LOG_COMPARE',
        'ARCHIVE_PROJECT'
    ));
