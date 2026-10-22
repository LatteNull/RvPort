--liquibase formatted sql

--changeset rvport:0126-specialized-analysis-task-types
ALTER TABLE tasks
    DROP CONSTRAINT IF EXISTS tasks_type_chk;

ALTER TABLE tasks
    ADD CONSTRAINT tasks_type_chk CHECK (type IN (
        'SOURCE_GIT_SYNC',
        'SOURCE_DEPLOY',
        'ENV_TEST_CONNECTION',
        'ENV_COLLECT',
        'ENV_RUN_SCRIPT',
        'DEPENDENCY_ANALYSIS',
        'DEPENDENCY_AUTO_FIX',
        'KB_SCAN',
        'REPORT_GENERATE',
        'REPORT_COMPARE',
        'RECHECK_DIFF',
        'BUILD_VALIDATION',
        'AUTOMATED_TEST',
        'TEST_LOG_COMPARE',
        'ARCHIVE_PROJECT',
        'KB_AI_EXTENSION',
        'FLOATING_POINT_ANALYSIS',
        'MEMORY_ORDER_ANALYSIS'
    ));

--changeset rvport:0126-specialized-analysis-artifact-owner
ALTER TABLE stored_artifacts
    DROP CONSTRAINT IF EXISTS stored_artifacts_owner_type_chk;

ALTER TABLE stored_artifacts
    ADD CONSTRAINT stored_artifacts_owner_type_chk CHECK (owner_type IN (
        'KB_SCAN',
        'DEPENDENCY_ANALYSIS',
        'BUILD_VALIDATION',
        'MIGRATION_REPORT',
        'ARCHIVE',
        'AUTOMATED_TEST',
        'TEST_COMPARISON',
        'KB_AI_EXTENSION',
        'SPECIALIZED_ANALYSIS'
    ));

--changeset rvport:0126-specialized-analysis-runs
CREATE TABLE specialized_analysis_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id),
    task_id uuid UNIQUE REFERENCES tasks(id),
    analyzer_type text NOT NULL,
    source_revision_id uuid NOT NULL REFERENCES source_revisions(id),
    build_run_id uuid NOT NULL REFERENCES build_runs(id),
    artifact_set_id text NOT NULL,
    environment_config_version bigint,
    tool_version text,
    request_schema_version text NOT NULL,
    result_schema_version text NOT NULL,
    policy_id text,
    status text NOT NULL,
    verdict text,
    exit_code integer,
    summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    request_artifact_id uuid REFERENCES stored_artifacts(id) ON DELETE SET NULL,
    result_json_artifact_id uuid REFERENCES stored_artifacts(id) ON DELETE SET NULL,
    result_html_artifact_id uuid REFERENCES stored_artifacts(id) ON DELETE SET NULL,
    audit_bundle_artifact_id uuid REFERENCES stored_artifacts(id) ON DELETE SET NULL,
    finding_count integer NOT NULL DEFAULT 0,
    candidate_count integer NOT NULL DEFAULT 0,
    diagnostic_count integer NOT NULL DEFAULT 0,
    created_by uuid REFERENCES users(id),
    started_at timestamptz,
    finished_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT specialized_analysis_runs_analyzer_chk
        CHECK (analyzer_type IN ('FLOATING_POINT', 'MEMORY_ORDER')),
    CONSTRAINT specialized_analysis_runs_status_chk
        CHECK (status IN ('PENDING', 'QUEUED', 'RUNNING', 'COMPLETE', 'COMPLETE_WITH_RISK', 'PARTIAL', 'FAILED', 'CANCELLED', 'TIMEOUT')),
    CONSTRAINT specialized_analysis_runs_counts_chk
        CHECK (finding_count >= 0 AND candidate_count >= 0 AND diagnostic_count >= 0),
    CONSTRAINT specialized_analysis_runs_environment_version_chk
        CHECK (environment_config_version IS NULL OR environment_config_version > 0)
);

CREATE INDEX specialized_analysis_runs_project_analyzer_created_idx
    ON specialized_analysis_runs(project_id, analyzer_type, created_at DESC, id DESC);

CREATE INDEX specialized_analysis_runs_project_source_analyzer_status_idx
    ON specialized_analysis_runs(project_id, source_revision_id, analyzer_type, status, created_at DESC, id DESC);

CREATE INDEX specialized_analysis_runs_build_idx
    ON specialized_analysis_runs(build_run_id);

CREATE INDEX specialized_analysis_runs_task_idx
    ON specialized_analysis_runs(task_id);

--changeset rvport:0126-specialized-analysis-findings
CREATE TABLE specialized_analysis_findings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL REFERENCES specialized_analysis_runs(id) ON DELETE CASCADE,
    project_id uuid NOT NULL REFERENCES projects(id),
    source_revision_id uuid NOT NULL REFERENCES source_revisions(id),
    analyzer_type text NOT NULL,
    external_finding_id text NOT NULL,
    finding_kind text NOT NULL,
    finding_code text,
    category text,
    severity text NOT NULL,
    confidence text,
    result_status text NOT NULL,
    title text NOT NULL,
    title_en text,
    message text,
    message_en text,
    suggestion text,
    suggestion_en text,
    test_suggestion text,
    test_suggestion_en text,
    file_path text,
    start_line integer,
    start_column integer,
    end_line integer,
    end_column integer,
    requires_human_confirmation boolean NOT NULL DEFAULT false,
    semantic_digest text,
    detail jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT specialized_analysis_findings_analyzer_chk
        CHECK (analyzer_type IN ('FLOATING_POINT', 'MEMORY_ORDER')),
    CONSTRAINT specialized_analysis_findings_severity_chk
        CHECK (severity IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO', 'COMMENT')),
    CONSTRAINT specialized_analysis_findings_position_chk
        CHECK ((start_line IS NULL OR start_line > 0)
            AND (start_column IS NULL OR start_column > 0)
            AND (end_line IS NULL OR end_line > 0)
            AND (end_column IS NULL OR end_column > 0)),
    CONSTRAINT specialized_analysis_findings_run_external_uk
        UNIQUE (run_id, external_finding_id)
);

CREATE INDEX specialized_analysis_findings_run_created_idx
    ON specialized_analysis_findings(run_id, created_at DESC, id DESC);

CREATE INDEX specialized_analysis_findings_project_analyzer_severity_idx
    ON specialized_analysis_findings(project_id, analyzer_type, severity, created_at DESC, id DESC);

CREATE INDEX specialized_analysis_findings_run_status_code_idx
    ON specialized_analysis_findings(run_id, result_status, finding_code, id);

CREATE INDEX specialized_analysis_findings_run_path_line_idx
    ON specialized_analysis_findings(run_id, file_path, start_line, id)
    WHERE file_path IS NOT NULL;

--changeset rvport:0126-specialized-analysis-migration-input-types
ALTER TABLE migration_input_refs
    DROP CONSTRAINT IF EXISTS migration_input_refs_source_type_chk;

ALTER TABLE migration_input_refs
    ADD CONSTRAINT migration_input_refs_source_type_chk CHECK (source_type IN (
        'KB_FINDING',
        'DEPENDENCY_RESULT',
        'FLOATING_POINT_FINDING',
        'MEMORY_ORDER_FINDING'
    ));
