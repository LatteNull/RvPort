--liquibase formatted sql

--changeset rvport:0094-migration-input-identity
ALTER TABLE migration_input_refs
    ADD COLUMN IF NOT EXISTS rule_id text,
    ADD COLUMN IF NOT EXISTS identity_path text,
    ADD COLUMN IF NOT EXISTS identity_symbol text,
    ADD COLUMN IF NOT EXISTS identity_anchor text,
    ADD COLUMN IF NOT EXISTS stable_fingerprint text;

CREATE INDEX IF NOT EXISTS migration_input_refs_project_revision_fingerprint_idx
    ON migration_input_refs(project_id, source_revision_id, stable_fingerprint);

--changeset rvport:0094-diff-item-summary
ALTER TABLE diff_items
    ADD COLUMN IF NOT EXISTS title text,
    ADD COLUMN IF NOT EXISTS location_label text,
    ADD COLUMN IF NOT EXISTS recommendation text,
    ADD COLUMN IF NOT EXISTS confirmation_status text,
    ADD COLUMN IF NOT EXISTS match_confidence text,
    ADD COLUMN IF NOT EXISTS match_reason text,
    ADD COLUMN IF NOT EXISTS old_snapshot jsonb,
    ADD COLUMN IF NOT EXISTS new_snapshot jsonb;

ALTER TABLE diff_items
    DROP CONSTRAINT IF EXISTS diff_items_match_confidence_chk;

ALTER TABLE diff_items
    ADD CONSTRAINT diff_items_match_confidence_chk
        CHECK (match_confidence IS NULL OR match_confidence IN ('HIGH', 'MEDIUM', 'LOW'));

CREATE INDEX IF NOT EXISTS diff_items_project_recheck_status_idx
    ON diff_items(project_id, recheck_run_id, diff_status);

CREATE INDEX IF NOT EXISTS diff_items_project_recheck_confidence_idx
    ON diff_items(project_id, recheck_run_id, match_confidence);

CREATE INDEX IF NOT EXISTS diff_items_project_recheck_severity_idx
    ON diff_items(project_id, recheck_run_id, severity);

--changeset rvport:0094-recheck-run-unique-pair
CREATE UNIQUE INDEX IF NOT EXISTS recheck_runs_project_base_target_nonfailed_uidx
    ON recheck_runs(project_id, base_source_revision_id, target_source_revision_id)
    WHERE status IN ('PENDING', 'QUEUED', 'RUNNING', 'SUCCEEDED');
