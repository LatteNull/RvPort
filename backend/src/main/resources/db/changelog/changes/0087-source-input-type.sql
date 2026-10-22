--liquibase formatted sql

--changeset rvport:0087-source-input-type splitStatements:false
ALTER TABLE projects
    ADD COLUMN IF NOT EXISTS source_input_type text;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'projects_source_input_type_chk'
    ) THEN
        ALTER TABLE projects
            ADD CONSTRAINT projects_source_input_type_chk
            CHECK (source_input_type IS NULL OR source_input_type IN ('ARCHIVE', 'GIT'));
    END IF;
END $$;

UPDATE projects p
SET source_input_type = active_revision.revision_type
FROM (
    SELECT DISTINCT ON (project_id)
        project_id,
        revision_type
    FROM source_revisions
    WHERE is_active = true
    ORDER BY project_id, created_at ASC, id ASC
) active_revision
WHERE p.id = active_revision.project_id
  AND p.source_input_type IS NULL;

UPDATE projects p
SET source_input_type = first_revision.revision_type
FROM (
    SELECT DISTINCT ON (project_id)
        project_id,
        revision_type
    FROM source_revisions
    ORDER BY project_id, created_at ASC, id ASC
) first_revision
WHERE p.id = first_revision.project_id
  AND p.source_input_type IS NULL;

CREATE INDEX IF NOT EXISTS projects_source_input_type_idx ON projects (source_input_type);
