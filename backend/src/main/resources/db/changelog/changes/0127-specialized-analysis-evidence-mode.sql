--liquibase formatted sql

--changeset rvport:0127-specialized-analysis-evidence-mode
ALTER TABLE specialized_analysis_runs
    ALTER COLUMN artifact_set_id DROP NOT NULL,
    ADD COLUMN analysis_mode text NOT NULL DEFAULT 'AST_ONLY',
    ADD COLUMN bc_status text NOT NULL DEFAULT 'UNKNOWN',
    ADD COLUMN bc_planned_count integer NOT NULL DEFAULT 0,
    ADD COLUMN bc_usable_count integer NOT NULL DEFAULT 0,
    ADD COLUMN bc_failed_count integer NOT NULL DEFAULT 0,
    ADD COLUMN bc_degradation_reason text,
    ADD CONSTRAINT specialized_analysis_runs_analysis_mode_chk
        CHECK (analysis_mode IN ('AST_ONLY', 'AST_BC_MIXED', 'AST_BC_COMPLETE')),
    ADD CONSTRAINT specialized_analysis_runs_bc_counts_chk
        CHECK (bc_planned_count >= 0 AND bc_usable_count >= 0 AND bc_failed_count >= 0
            AND bc_usable_count <= bc_planned_count AND bc_failed_count <= bc_planned_count);

UPDATE specialized_analysis_runs
SET analysis_mode = CASE
        WHEN artifact_set_id IS NULL THEN 'AST_ONLY'
        ELSE 'AST_BC_MIXED'
    END,
    bc_status = CASE
        WHEN artifact_set_id IS NULL THEN 'LEGACY_MISSING'
        ELSE 'LEGACY_UNKNOWN'
    END;
