--liquibase formatted sql

--changeset rvport:0050-kb-scan-runs
CREATE TABLE kb_scan_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id),
    task_id uuid NOT NULL UNIQUE REFERENCES tasks(id),
    source_revision_id uuid NOT NULL REFERENCES source_revisions(id),
    kb_version text,
    scope jsonb NOT NULL,
    status text NOT NULL,
    summary jsonb,
    started_at timestamptz,
    finished_at timestamptz,
    CONSTRAINT kb_scan_runs_status_chk CHECK (status IN ('PENDING', 'QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'TIMEOUT'))
);

CREATE INDEX kb_scan_runs_project_started_idx ON kb_scan_runs (project_id, started_at DESC);
CREATE INDEX kb_scan_runs_source_revision_idx ON kb_scan_runs (source_revision_id);

--changeset rvport:0051-findings
CREATE TABLE findings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id),
    scan_run_id uuid NOT NULL REFERENCES kb_scan_runs(id),
    source_revision_id uuid NOT NULL REFERENCES source_revisions(id),
    rule_id text NOT NULL,
    category text NOT NULL,
    severity text NOT NULL,
    title text NOT NULL,
    description text,
    file_path text,
    line_start integer,
    line_end integer,
    symbol text,
    evidence jsonb,
    suggestion text,
    fingerprint text NOT NULL,
    status text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT findings_line_start_chk CHECK (line_start IS NULL OR line_start > 0),
    CONSTRAINT findings_line_end_chk CHECK (line_end IS NULL OR line_end > 0),
    CONSTRAINT findings_line_range_chk CHECK (line_start IS NULL OR line_end IS NULL OR line_end >= line_start),
    CONSTRAINT findings_status_chk CHECK (status IN ('DETECTED', 'SUPPRESSED'))
);

CREATE INDEX findings_project_severity_idx ON findings (project_id, severity);
CREATE INDEX findings_scan_run_idx ON findings (scan_run_id);
CREATE INDEX findings_source_revision_idx ON findings (source_revision_id);
CREATE INDEX findings_fingerprint_idx ON findings (fingerprint);
CREATE INDEX findings_file_path_idx ON findings (file_path);

