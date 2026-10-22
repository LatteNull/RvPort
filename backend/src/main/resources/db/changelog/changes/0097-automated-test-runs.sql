--liquibase formatted sql

--changeset rvport:0097-automated-test-runs
ALTER TABLE test_runs
    ADD COLUMN IF NOT EXISTS output_summary text,
    ADD COLUMN IF NOT EXISTS report_artifacts jsonb NOT NULL DEFAULT '[]'::jsonb;

CREATE INDEX IF NOT EXISTS test_runs_status_idx ON test_runs (status);
CREATE INDEX IF NOT EXISTS test_runs_source_revision_idx ON test_runs (source_revision_id);

ALTER TABLE stored_artifacts
    DROP CONSTRAINT IF EXISTS stored_artifacts_owner_type_chk;

ALTER TABLE stored_artifacts
    ADD CONSTRAINT stored_artifacts_owner_type_chk
        CHECK (owner_type IN ('KB_SCAN', 'MIGRATION_REPORT', 'ARCHIVE', 'AUTOMATED_TEST'));
