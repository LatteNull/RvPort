--liquibase formatted sql

--changeset rvport:0125-report-input-organization
ALTER TABLE report_inputs
    ADD COLUMN source_type text,
    ADD COLUMN risk_level text,
    ADD COLUMN module_key text,
    ADD COLUMN module_name text,
    ADD COLUMN module_basis text,
    ADD COLUMN module_confidence text,
    ADD COLUMN related_module_keys jsonb,
    ADD COLUMN file_key text,
    ADD COLUMN relative_path text,
    ADD COLUMN finding_type text,
    ADD COLUMN line_start integer,
    ADD COLUMN line_end integer,
    ADD COLUMN column_start integer,
    ADD COLUMN column_end integer,
    ADD COLUMN symbol text,
    ADD COLUMN source_content_hash text,
    ADD COLUMN location_available boolean;

CREATE INDEX report_inputs_report_module_idx
    ON report_inputs (report_id, module_key)
    WHERE module_key IS NOT NULL;

CREATE INDEX report_inputs_report_file_type_line_idx
    ON report_inputs (report_id, file_key, finding_type, line_start, line_end, id)
    WHERE file_key IS NOT NULL;

CREATE INDEX report_inputs_report_risk_idx
    ON report_inputs (report_id, risk_level)
    WHERE risk_level IS NOT NULL;

--changeset rvport:0125-report-file-contexts
CREATE TABLE report_file_contexts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id uuid NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    source_revision_id uuid NOT NULL REFERENCES source_revisions(id),
    file_key text NOT NULL,
    relative_path text NOT NULL,
    content_hash text,
    total_lines integer,
    artifact_id uuid REFERENCES stored_artifacts(id) ON DELETE SET NULL,
    context_available boolean NOT NULL DEFAULT false,
    unavailable_reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT report_file_contexts_report_file_uk UNIQUE (report_id, file_key),
    CONSTRAINT report_file_contexts_total_lines_chk CHECK (total_lines IS NULL OR total_lines >= 0)
);

CREATE INDEX report_file_contexts_report_path_idx
    ON report_file_contexts (report_id, relative_path);
