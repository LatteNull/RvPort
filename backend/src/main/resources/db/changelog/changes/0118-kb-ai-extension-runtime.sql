--liquibase formatted sql

--changeset rvport:0118-kb-ai-extension-stage
ALTER TABLE model_stage_assignments
    DROP CONSTRAINT IF EXISTS model_stage_assignments_stage_chk;

ALTER TABLE model_stage_assignments
    ADD CONSTRAINT model_stage_assignments_stage_chk
        CHECK (stage IN ('TEST_LOG_COMPARE', 'KB_AI_EXTENSION'));

ALTER TABLE model_profile_agent_probe_results
    ADD COLUMN IF NOT EXISTS kb_ai_extension_compatible boolean;

--changeset rvport:0118-kb-ai-extension-task-type
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
        'KB_AI_EXTENSION'
    ));

--changeset rvport:0118-kb-ai-extension-artifact-owner
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
        'KB_AI_EXTENSION'
    ));

--changeset rvport:0118-kb-ai-extension-runs
CREATE TABLE IF NOT EXISTS kb_ai_extension_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id),
    source_revision_id uuid NOT NULL REFERENCES source_revisions(id),
    kb_scan_run_id uuid NOT NULL REFERENCES kb_scan_runs(id) ON DELETE CASCADE,
    task_id uuid UNIQUE REFERENCES tasks(id),
    model_profile_id uuid REFERENCES model_profiles(id),
    agent_runtime_id uuid REFERENCES agent_runtimes(id),
    status text NOT NULL,
    summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    input_artifact_id uuid REFERENCES stored_artifacts(id),
    output_artifact_id uuid REFERENCES stored_artifacts(id),
    agent_output_artifact_id uuid REFERENCES stored_artifacts(id),
    created_by uuid REFERENCES users(id),
    started_at timestamptz,
    finished_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT kb_ai_extension_runs_status_chk
        CHECK (status IN ('PENDING', 'QUEUED', 'RUNNING', 'SUCCEEDED', 'PARTIAL_SUCCESS', 'FAILED', 'CANCELLED', 'TIMEOUT'))
);

CREATE INDEX IF NOT EXISTS kb_ai_extension_runs_project_created_idx
    ON kb_ai_extension_runs(project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS kb_ai_extension_runs_scan_created_idx
    ON kb_ai_extension_runs(kb_scan_run_id, created_at DESC);

CREATE INDEX IF NOT EXISTS kb_ai_extension_runs_source_status_idx
    ON kb_ai_extension_runs(source_revision_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS kb_ai_extension_runs_task_idx
    ON kb_ai_extension_runs(task_id);

--changeset rvport:0118-kb-ai-extension-results
CREATE TABLE IF NOT EXISTS kb_ai_extension_results (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL REFERENCES kb_ai_extension_runs(id) ON DELETE CASCADE,
    project_id uuid NOT NULL REFERENCES projects(id),
    source_revision_id uuid NOT NULL REFERENCES source_revisions(id),
    kb_scan_run_id uuid NOT NULL REFERENCES kb_scan_runs(id) ON DELETE CASCADE,
    finding_id uuid NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
    ai_summary text,
    ai_suggestion text,
    confidence numeric(5,4),
    action_type text,
    raw_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT kb_ai_extension_results_confidence_chk CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
);

CREATE UNIQUE INDEX IF NOT EXISTS kb_ai_extension_results_run_finding_uidx
    ON kb_ai_extension_results(run_id, finding_id);

CREATE INDEX IF NOT EXISTS kb_ai_extension_results_scan_finding_idx
    ON kb_ai_extension_results(kb_scan_run_id, finding_id);

CREATE INDEX IF NOT EXISTS kb_ai_extension_results_project_created_idx
    ON kb_ai_extension_results(project_id, created_at DESC);

--changeset rvport:0118-kb-ai-extension-run-config-fk-delete
ALTER TABLE kb_ai_extension_runs
    DROP CONSTRAINT IF EXISTS kb_ai_extension_runs_model_profile_id_fkey;

ALTER TABLE kb_ai_extension_runs
    ADD CONSTRAINT kb_ai_extension_runs_model_profile_id_fkey
        FOREIGN KEY (model_profile_id) REFERENCES model_profiles(id) ON DELETE SET NULL;

ALTER TABLE kb_ai_extension_runs
    DROP CONSTRAINT IF EXISTS kb_ai_extension_runs_agent_runtime_id_fkey;

ALTER TABLE kb_ai_extension_runs
    ADD CONSTRAINT kb_ai_extension_runs_agent_runtime_id_fkey
        FOREIGN KEY (agent_runtime_id) REFERENCES agent_runtimes(id) ON DELETE SET NULL;
