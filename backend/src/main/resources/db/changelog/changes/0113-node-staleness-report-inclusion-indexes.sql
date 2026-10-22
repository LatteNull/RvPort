--liquibase formatted sql

--changeset rvport:0113-node-staleness-report-inclusion-indexes
CREATE INDEX IF NOT EXISTS build_runs_project_revision_env_created_idx
    ON build_runs(project_id, source_revision_id, environment_config_version, created_at DESC);

CREATE INDEX IF NOT EXISTS dependency_analysis_runs_project_revision_env_created_idx
    ON dependency_analysis_runs(project_id, source_revision_id, environment_config_version, created_at DESC);

CREATE INDEX IF NOT EXISTS kb_scan_runs_project_revision_started_idx
    ON kb_scan_runs(project_id, source_revision_id, started_at DESC);

CREATE INDEX IF NOT EXISTS migration_input_refs_project_revision_source_ref_idx
    ON migration_input_refs(project_id, source_revision_id, source_type, source_ref_id);

CREATE INDEX IF NOT EXISTS report_inputs_report_type_input_idx
    ON report_inputs(report_id, input_type, input_id);
