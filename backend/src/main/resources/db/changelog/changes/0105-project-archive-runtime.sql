--liquibase formatted sql

--changeset rvport:0105-archive-candidates
CREATE TABLE IF NOT EXISTS archive_candidates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    source_revision_id uuid NOT NULL REFERENCES source_revisions(id) ON DELETE CASCADE,
    node_type text NOT NULL,
    candidate_type text NOT NULL,
    candidate_key text NOT NULL,
    resource_type text NOT NULL,
    resource_id uuid,
    title text NOT NULL,
    summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    artifact_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    status text NOT NULL DEFAULT 'ACTIVE',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT archive_candidates_status_chk CHECK (status IN ('ACTIVE', 'SUPERSEDED', 'DELETED')),
    CONSTRAINT archive_candidates_slot_uk UNIQUE (project_id, source_revision_id, node_type, candidate_type, candidate_key)
);

CREATE INDEX IF NOT EXISTS archive_candidates_project_revision_status_idx
    ON archive_candidates(project_id, source_revision_id, status);

CREATE INDEX IF NOT EXISTS archive_candidates_project_revision_type_idx
    ON archive_candidates(project_id, source_revision_id, node_type, candidate_type);

CREATE INDEX IF NOT EXISTS archive_candidates_resource_idx
    ON archive_candidates(resource_type, resource_id);

--changeset rvport:0106-archives-source-revision
ALTER TABLE archives
    ADD COLUMN IF NOT EXISTS source_revision_id uuid REFERENCES source_revisions(id),
    ADD COLUMN IF NOT EXISTS stored_artifact_id uuid REFERENCES stored_artifacts(id),
    ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS archives_project_revision_created_idx
    ON archives(project_id, source_revision_id, created_at DESC);

CREATE INDEX IF NOT EXISTS archives_project_status_created_idx
    ON archives(project_id, status, created_at DESC);

--changeset rvport:0107-archive-items-candidate-snapshot
ALTER TABLE archive_items
    ADD COLUMN IF NOT EXISTS candidate_id uuid REFERENCES archive_candidates(id),
    ADD COLUMN IF NOT EXISTS node_type text,
    ADD COLUMN IF NOT EXISTS candidate_type text,
    ADD COLUMN IF NOT EXISTS candidate_key text,
    ADD COLUMN IF NOT EXISTS resource_type text,
    ADD COLUMN IF NOT EXISTS resource_id uuid,
    ADD COLUMN IF NOT EXISTS title text,
    ADD COLUMN IF NOT EXISTS artifact_refs jsonb NOT NULL DEFAULT '[]'::jsonb;

UPDATE archive_items
SET resource_type = item_type
WHERE resource_type IS NULL;

CREATE INDEX IF NOT EXISTS archive_items_archive_type_idx
    ON archive_items(archive_id, node_type, candidate_type);

CREATE INDEX IF NOT EXISTS archive_items_candidate_idx
    ON archive_items(candidate_id);

--changeset rvport:0108-archive-task-type
ALTER TABLE tasks
    DROP CONSTRAINT IF EXISTS tasks_type_chk;

ALTER TABLE tasks
    ADD CONSTRAINT tasks_type_chk CHECK (type IN (
        'SOURCE_GIT_SYNC',
        'SOURCE_DEPLOY',
        'ENV_TEST_CONNECTION',
        'ENV_COLLECT',
        'ENV_RUN_SCRIPT',
        'KB_SCAN',
        'REPORT_GENERATE',
        'RECHECK_DIFF',
        'BUILD_VALIDATION',
        'AUTOMATED_TEST',
        'TEST_LOG_COMPARE',
        'ARCHIVE_PROJECT'
    ));
