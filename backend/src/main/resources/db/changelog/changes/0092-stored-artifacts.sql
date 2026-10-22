--liquibase formatted sql

--changeset rvport:0092-stored-artifacts
CREATE TABLE stored_artifacts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id),
    task_id uuid REFERENCES tasks(id),
    owner_type text NOT NULL,
    owner_id uuid NOT NULL,
    artifact_type text NOT NULL,
    bucket text NOT NULL,
    object_key text NOT NULL,
    content_type text NOT NULL,
    size_bytes bigint NOT NULL,
    sha256 text NOT NULL,
    summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT stored_artifacts_owner_type_chk CHECK (owner_type IN ('KB_SCAN', 'MIGRATION_REPORT', 'ARCHIVE')),
    CONSTRAINT stored_artifacts_size_chk CHECK (size_bytes >= 0),
    CONSTRAINT stored_artifacts_owner_type_uk UNIQUE (owner_type, owner_id, artifact_type),
    CONSTRAINT stored_artifacts_object_key_uk UNIQUE (bucket, object_key)
);

CREATE INDEX stored_artifacts_project_created_idx ON stored_artifacts (project_id, created_at DESC);
CREATE INDEX stored_artifacts_task_idx ON stored_artifacts (task_id);
CREATE INDEX stored_artifacts_owner_idx ON stored_artifacts (owner_type, owner_id);

--changeset rvport:0092-artifact-compat-fields
ALTER TABLE kb_scan_artifacts
    ADD COLUMN stored_artifact_id uuid REFERENCES stored_artifacts(id);

CREATE INDEX kb_scan_artifacts_stored_artifact_idx ON kb_scan_artifacts (stored_artifact_id);


