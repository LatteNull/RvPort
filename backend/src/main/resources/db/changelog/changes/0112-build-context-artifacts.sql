--liquibase formatted sql

--changeset rvport:0112-build-context-artifacts-owner-type
ALTER TABLE stored_artifacts
    DROP CONSTRAINT IF EXISTS stored_artifacts_owner_type_chk;

ALTER TABLE stored_artifacts
    ADD CONSTRAINT stored_artifacts_owner_type_chk CHECK (owner_type IN (
        'KB_SCAN',
        'DEPENDENCY_ANALYSIS',
        'BUILD_VALIDATION',
        'MIGRATION_REPORT',
        'ARCHIVE',
        'AUTOMATED_TEST',
        'TEST_COMPARISON'
    ));

--changeset rvport:0112-build-context-query-index
CREATE INDEX IF NOT EXISTS build_runs_context_lookup_idx
    ON build_runs(project_id, source_revision_id, build_scope, status, finished_at DESC);
