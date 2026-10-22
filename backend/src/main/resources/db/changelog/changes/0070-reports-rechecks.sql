--liquibase formatted sql

--changeset rvport:0070-reports
CREATE TABLE reports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id),
    task_id uuid NOT NULL UNIQUE REFERENCES tasks(id),
    report_type text NOT NULL,
    status text NOT NULL,
    title text NOT NULL,
    summary jsonb,
    risk_level text,
    html_path text,
    json_path text,
    generated_by uuid NOT NULL REFERENCES users(id),
    generated_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT reports_type_chk CHECK (report_type IN ('EVALUATION', 'DIFF')),
    CONSTRAINT reports_status_chk CHECK (status IN ('PENDING', 'QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'TIMEOUT'))
);

CREATE INDEX reports_project_generated_idx ON reports (project_id, generated_at DESC);
CREATE INDEX reports_type_idx ON reports (report_type);

--changeset rvport:0071-report-inputs
CREATE TABLE report_inputs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id uuid NOT NULL REFERENCES reports(id),
    input_type text NOT NULL,
    input_id uuid NOT NULL,
    input_snapshot jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX report_inputs_report_idx ON report_inputs (report_id);
CREATE INDEX report_inputs_input_idx ON report_inputs (input_type, input_id);

--changeset rvport:0072-recheck-runs
CREATE TABLE recheck_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id),
    task_id uuid NOT NULL UNIQUE REFERENCES tasks(id),
    base_source_revision_id uuid NOT NULL REFERENCES source_revisions(id),
    target_source_revision_id uuid NOT NULL REFERENCES source_revisions(id),
    base_scan_run_id uuid REFERENCES kb_scan_runs(id),
    target_scan_run_id uuid REFERENCES kb_scan_runs(id),
    summary jsonb,
    status text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT recheck_runs_status_chk CHECK (status IN ('PENDING', 'QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'TIMEOUT'))
);

CREATE INDEX recheck_runs_project_created_idx ON recheck_runs (project_id, created_at DESC);

--changeset rvport:0073-diff-items
CREATE TABLE diff_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    recheck_run_id uuid NOT NULL REFERENCES recheck_runs(id),
    project_id uuid NOT NULL REFERENCES projects(id),
    source_type text NOT NULL,
    old_source_id uuid,
    new_source_id uuid,
    diff_status text NOT NULL,
    old_location jsonb,
    new_location jsonb,
    severity text,
    fingerprint text,
    CONSTRAINT diff_items_status_chk CHECK (diff_status IN ('NEW', 'RESOLVED', 'UNCHANGED', 'CHANGED'))
);

CREATE INDEX diff_items_recheck_run_idx ON diff_items (recheck_run_id);
CREATE INDEX diff_items_project_status_idx ON diff_items (project_id, diff_status);
CREATE INDEX diff_items_fingerprint_idx ON diff_items (fingerprint);
