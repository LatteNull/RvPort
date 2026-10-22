--liquibase formatted sql

--changeset rvport:0090-migration-input-sets
CREATE TABLE migration_input_sets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id),
    source_revision_id uuid NOT NULL REFERENCES source_revisions(id),
    status text NOT NULL DEFAULT 'ACTIVE',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz,
    CONSTRAINT migration_input_sets_status_chk CHECK (status IN ('ACTIVE', 'ARCHIVED'))
);

CREATE UNIQUE INDEX migration_input_sets_source_revision_active_uidx
    ON migration_input_sets(source_revision_id)
    WHERE status = 'ACTIVE';

CREATE INDEX migration_input_sets_project_source_revision_idx
    ON migration_input_sets(project_id, source_revision_id);

--changeset rvport:0090-migration-input-refs
CREATE TABLE migration_input_refs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    input_set_id uuid NOT NULL REFERENCES migration_input_sets(id),
    project_id uuid NOT NULL REFERENCES projects(id),
    source_revision_id uuid NOT NULL REFERENCES source_revisions(id),
    issue_title text NOT NULL,
    source_type text NOT NULL,
    source_ref_id uuid NOT NULL,
    detected_level text NOT NULL,
    location_label text,
    recommendation_summary text,
    status text NOT NULL DEFAULT 'CANDIDATE',
    note text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz,
    CONSTRAINT migration_input_refs_source_type_chk CHECK (source_type IN ('KB_FINDING')),
    CONSTRAINT migration_input_refs_status_chk CHECK (status IN ('CANDIDATE', 'CONFIRMED', 'EXCLUDED'))
);

CREATE UNIQUE INDEX migration_input_refs_set_source_uidx
    ON migration_input_refs(input_set_id, source_type, source_ref_id);

CREATE INDEX migration_input_refs_project_source_revision_created_idx
    ON migration_input_refs(project_id, source_revision_id, created_at DESC);

CREATE INDEX migration_input_refs_project_source_revision_source_type_idx
    ON migration_input_refs(project_id, source_revision_id, source_type);

CREATE INDEX migration_input_refs_project_source_revision_status_idx
    ON migration_input_refs(project_id, source_revision_id, status);

CREATE INDEX migration_input_refs_project_source_revision_detected_level_idx
    ON migration_input_refs(project_id, source_revision_id, detected_level);
