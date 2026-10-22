--liquibase formatted sql

--changeset rvport:0089-kb-scan-artifacts
CREATE TABLE kb_scan_artifacts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id),
    task_id uuid NOT NULL REFERENCES tasks(id),
    scan_run_id uuid NOT NULL REFERENCES kb_scan_runs(id) ON DELETE CASCADE,
    artifact_type text NOT NULL,
    schema_version text,
    sha256 text NOT NULL,
    size_bytes bigint NOT NULL,
    content_path text NOT NULL,
    summary jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT kb_scan_artifacts_type_chk CHECK (artifact_type IN ('SCAN_RESULT_JSON', 'SCAN_REPORT_HTML', 'SCAN_LOG')),
    CONSTRAINT kb_scan_artifacts_size_chk CHECK (size_bytes >= 0),
    CONSTRAINT kb_scan_artifacts_unique_type UNIQUE (scan_run_id, artifact_type)
);

CREATE INDEX kb_scan_artifacts_scan_run_idx ON kb_scan_artifacts (scan_run_id);
CREATE INDEX kb_scan_artifacts_task_idx ON kb_scan_artifacts (task_id);
CREATE INDEX kb_scan_artifacts_project_created_idx ON kb_scan_artifacts (project_id, created_at DESC);

--changeset rvport:0089-kb-scan-query-indexes
CREATE INDEX kb_scan_runs_project_status_started_idx ON kb_scan_runs (project_id, status, started_at DESC);
CREATE INDEX findings_scan_severity_idx ON findings (scan_run_id, severity);
CREATE INDEX findings_scan_file_line_idx ON findings (scan_run_id, file_path, line_start);
