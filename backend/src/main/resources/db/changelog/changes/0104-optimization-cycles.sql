--liquibase formatted sql

--changeset rvport:0104-optimization-cycles
CREATE TABLE IF NOT EXISTS optimization_cycles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    source_revision_id uuid NOT NULL REFERENCES source_revisions(id) ON DELETE CASCADE,
    cycle_number integer NOT NULL,
    status text NOT NULL DEFAULT 'ACTIVE',
    summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    started_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT optimization_cycles_status_chk CHECK (status IN ('ACTIVE', 'SUPERSEDED', 'ARCHIVED')),
    CONSTRAINT optimization_cycles_cycle_number_chk CHECK (cycle_number > 0),
    CONSTRAINT optimization_cycles_project_revision_uidx UNIQUE (project_id, source_revision_id),
    CONSTRAINT optimization_cycles_project_number_uidx UNIQUE (project_id, cycle_number)
);

CREATE INDEX IF NOT EXISTS optimization_cycles_project_cycle_idx
    ON optimization_cycles(project_id, cycle_number DESC);

CREATE INDEX IF NOT EXISTS optimization_cycles_project_status_idx
    ON optimization_cycles(project_id, status);

CREATE INDEX IF NOT EXISTS optimization_cycles_source_revision_idx
    ON optimization_cycles(source_revision_id);

CREATE INDEX IF NOT EXISTS optimization_cycles_project_updated_idx
    ON optimization_cycles(project_id, updated_at DESC);

--changeset rvport:0105-optimization-cycles-history
INSERT INTO optimization_cycles (
    project_id,
    source_revision_id,
    cycle_number,
    status,
    started_at,
    created_at,
    updated_at
)
SELECT
    source.project_id,
    source.id,
    row_number() OVER (PARTITION BY source.project_id ORDER BY source.created_at ASC, source.id ASC)::integer,
    CASE WHEN source.is_active THEN 'ACTIVE' ELSE 'SUPERSEDED' END,
    source.created_at,
    source.created_at,
    now()
FROM source_revisions source
ON CONFLICT (project_id, source_revision_id) DO NOTHING;
