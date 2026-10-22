--liquibase formatted sql

--changeset rvport:0093-report-source-revision splitStatements:false
ALTER TABLE reports
    ADD COLUMN IF NOT EXISTS source_revision_id uuid;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'reports_source_revision_id_fkey'
    ) THEN
        ALTER TABLE reports
            ADD CONSTRAINT reports_source_revision_id_fkey
            FOREIGN KEY (source_revision_id) REFERENCES source_revisions(id);
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS reports_project_source_revision_generated_idx
    ON reports (project_id, source_revision_id, generated_at DESC);

--changeset rvport:0093-report-input-type-check splitStatements:false
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'report_inputs_type_chk'
    ) THEN
        ALTER TABLE report_inputs
            ADD CONSTRAINT report_inputs_type_chk
            CHECK (input_type IN ('MIGRATION_INPUT_REF'));
    END IF;
END
$$;
