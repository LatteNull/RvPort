--liquibase formatted sql

--changeset rvport:0100-test-run-comparison-batch
ALTER TABLE test_runs
    ADD COLUMN IF NOT EXISTS test_batch_id uuid,
    ADD COLUMN IF NOT EXISTS test_batch_role text;

ALTER TABLE test_runs
    DROP CONSTRAINT IF EXISTS test_runs_batch_role_chk;

ALTER TABLE test_runs
    ADD CONSTRAINT test_runs_batch_role_chk
        CHECK (test_batch_role IS NULL OR test_batch_role IN ('SOURCE', 'TARGET'));

CREATE INDEX IF NOT EXISTS test_runs_project_batch_idx
    ON test_runs(project_id, test_batch_id, started_at DESC);

CREATE INDEX IF NOT EXISTS test_runs_project_batch_role_idx
    ON test_runs(project_id, test_batch_id, test_batch_role);

--changeset rvport:0101-test-comparison-runs
CREATE TABLE IF NOT EXISTS test_comparison_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id),
    task_id uuid UNIQUE REFERENCES tasks(id),
    test_batch_id uuid,
    source_test_run_id uuid NOT NULL REFERENCES test_runs(id),
    target_test_run_id uuid NOT NULL REFERENCES test_runs(id),
    status text NOT NULL,
    overall_status text,
    risk_level text,
    confidence numeric(5,4),
    summary text,
    recommendation text,
    unavailable_code text,
    unavailable_message text,
    error_code text,
    error_message text,
    input_truncated boolean NOT NULL DEFAULT false,
    input_summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    agent_output_artifact_id uuid REFERENCES stored_artifacts(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT test_comparison_runs_distinct_runs_chk CHECK (source_test_run_id <> target_test_run_id),
    CONSTRAINT test_comparison_runs_confidence_chk CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    CONSTRAINT test_comparison_runs_status_chk CHECK (status IN ('PENDING', 'QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'TIMEOUT', 'UNAVAILABLE')),
    CONSTRAINT test_comparison_runs_overall_status_chk CHECK (overall_status IS NULL OR overall_status IN ('EQUIVALENT', 'DIFFERENT_ACCEPTABLE', 'DIFFERENT_BLOCKING', 'INCONCLUSIVE')),
    CONSTRAINT test_comparison_runs_risk_level_chk CHECK (risk_level IS NULL OR risk_level IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'))
);

CREATE UNIQUE INDEX IF NOT EXISTS test_comparison_runs_pair_uk
    ON test_comparison_runs(project_id, source_test_run_id, target_test_run_id);

CREATE UNIQUE INDEX IF NOT EXISTS test_comparison_runs_batch_uk
    ON test_comparison_runs(project_id, test_batch_id)
    WHERE test_batch_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS test_comparison_runs_project_created_idx
    ON test_comparison_runs(project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS test_comparison_runs_project_status_idx
    ON test_comparison_runs(project_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS test_comparison_runs_project_risk_idx
    ON test_comparison_runs(project_id, risk_level, created_at DESC);

CREATE INDEX IF NOT EXISTS test_comparison_runs_task_idx
    ON test_comparison_runs(task_id);

CREATE INDEX IF NOT EXISTS test_comparison_runs_source_idx
    ON test_comparison_runs(source_test_run_id);

CREATE INDEX IF NOT EXISTS test_comparison_runs_target_idx
    ON test_comparison_runs(target_test_run_id);

--changeset rvport:0102-test-comparison-findings
CREATE TABLE IF NOT EXISTS test_comparison_findings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    comparison_run_id uuid NOT NULL REFERENCES test_comparison_runs(id) ON DELETE CASCADE,
    sequence_no integer NOT NULL,
    difference_type text NOT NULL,
    severity text NOT NULL,
    confidence numeric(5,4),
    title text NOT NULL,
    description text,
    source_summary text,
    target_summary text,
    recommendation text,
    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT test_comparison_findings_sequence_chk CHECK (sequence_no > 0),
    CONSTRAINT test_comparison_findings_confidence_chk CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    CONSTRAINT test_comparison_findings_severity_chk CHECK (severity IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'))
);

CREATE UNIQUE INDEX IF NOT EXISTS test_comparison_findings_sequence_uk
    ON test_comparison_findings(comparison_run_id, sequence_no);

CREATE INDEX IF NOT EXISTS test_comparison_findings_run_created_idx
    ON test_comparison_findings(comparison_run_id, created_at ASC);

CREATE INDEX IF NOT EXISTS test_comparison_findings_run_severity_idx
    ON test_comparison_findings(comparison_run_id, severity, sequence_no ASC);

CREATE INDEX IF NOT EXISTS test_comparison_findings_type_idx
    ON test_comparison_findings(difference_type);

--changeset rvport:0103-test-comparison-artifacts
ALTER TABLE stored_artifacts
    DROP CONSTRAINT IF EXISTS stored_artifacts_owner_type_chk;

ALTER TABLE stored_artifacts
    ADD CONSTRAINT stored_artifacts_owner_type_chk
        CHECK (owner_type IN ('KB_SCAN', 'MIGRATION_REPORT', 'ARCHIVE', 'AUTOMATED_TEST', 'TEST_COMPARISON'));
