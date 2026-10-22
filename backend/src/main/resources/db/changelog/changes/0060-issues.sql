--liquibase formatted sql

--changeset rvport:0060-issues
CREATE TABLE issues (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id),
    title text NOT NULL,
    description text,
    severity text NOT NULL,
    priority text,
    status text NOT NULL,
    resolution text,
    latest_detection_status text,
    fingerprint text NOT NULL,
    created_by uuid NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz,
    CONSTRAINT issues_status_chk CHECK (status IN ('CANDIDATE', 'CONFIRMED', 'IGNORED', 'RESOLVED')),
    CONSTRAINT issues_latest_detection_status_chk CHECK (
        latest_detection_status IS NULL OR latest_detection_status IN ('PRESENT', 'RESOLVED', 'NEW', 'CHANGED', 'UNKNOWN')
    )
);

CREATE INDEX issues_project_status_idx ON issues (project_id, status);
CREATE INDEX issues_project_severity_idx ON issues (project_id, severity);
CREATE INDEX issues_fingerprint_idx ON issues (fingerprint);

--changeset rvport:0061-issue-sources
CREATE TABLE issue_sources (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    issue_id uuid NOT NULL REFERENCES issues(id),
    source_type text NOT NULL,
    source_id uuid NOT NULL,
    source_run_id uuid,
    evidence jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT issue_sources_type_chk CHECK (source_type IN ('FINDING'))
);

CREATE INDEX issue_sources_issue_idx ON issue_sources (issue_id);
CREATE INDEX issue_sources_source_idx ON issue_sources (source_type, source_id);

--changeset rvport:0062-issue-events
CREATE TABLE issue_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    issue_id uuid NOT NULL REFERENCES issues(id),
    project_id uuid NOT NULL REFERENCES projects(id),
    event_type text NOT NULL,
    from_status text,
    to_status text,
    comment text,
    created_by uuid NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT issue_events_from_status_chk CHECK (from_status IS NULL OR from_status IN ('CANDIDATE', 'CONFIRMED', 'IGNORED', 'RESOLVED')),
    CONSTRAINT issue_events_to_status_chk CHECK (to_status IS NULL OR to_status IN ('CANDIDATE', 'CONFIRMED', 'IGNORED', 'RESOLVED'))
);

CREATE INDEX issue_events_issue_created_idx ON issue_events (issue_id, created_at);
CREATE INDEX issue_events_project_created_idx ON issue_events (project_id, created_at DESC);
