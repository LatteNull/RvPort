--liquibase formatted sql

--changeset rvport:0115-model-profile-agent-probe-flow
ALTER TABLE model_profiles
    ADD COLUMN IF NOT EXISTS last_connectivity_status text,
    ADD COLUMN IF NOT EXISTS last_connectivity_message text,
    ADD COLUMN IF NOT EXISTS last_connectivity_details jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS last_connectivity_tested_at timestamptz,
    ADD COLUMN IF NOT EXISTS last_connectivity_duration_ms bigint;

ALTER TABLE model_profiles
    DROP CONSTRAINT IF EXISTS model_profiles_connectivity_status_chk;

ALTER TABLE model_profiles
    ADD CONSTRAINT model_profiles_connectivity_status_chk
        CHECK (last_connectivity_status IS NULL OR last_connectivity_status IN ('SUCCESS', 'FAILED', 'TIMEOUT'));

CREATE INDEX IF NOT EXISTS model_profiles_last_connectivity_tested_at_idx
    ON model_profiles(last_connectivity_tested_at DESC);

CREATE TABLE IF NOT EXISTS model_profile_agent_probe_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    model_profile_id uuid NOT NULL REFERENCES model_profiles(id) ON DELETE CASCADE,
    status text NOT NULL DEFAULT 'PENDING',
    selected_agent_runtime_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
    selected_agent_runtimes jsonb NOT NULL DEFAULT '[]'::jsonb,
    message text,
    created_by uuid REFERENCES users(id),
    started_at timestamptz,
    finished_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT model_profile_agent_probe_runs_status_chk
        CHECK (status IN ('PENDING', 'RUNNING', 'SUCCESS', 'PARTIAL_SUCCESS', 'FAILED', 'TIMEOUT'))
);

CREATE INDEX IF NOT EXISTS model_profile_agent_probe_runs_profile_created_idx
    ON model_profile_agent_probe_runs(model_profile_id, created_at DESC);

CREATE INDEX IF NOT EXISTS model_profile_agent_probe_runs_profile_active_idx
    ON model_profile_agent_probe_runs(model_profile_id, created_at DESC)
    WHERE status IN ('PENDING', 'RUNNING');

CREATE TABLE IF NOT EXISTS model_profile_agent_probe_results (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL REFERENCES model_profile_agent_probe_runs(id) ON DELETE CASCADE,
    model_profile_id uuid NOT NULL REFERENCES model_profiles(id) ON DELETE CASCADE,
    agent_runtime_id uuid NOT NULL REFERENCES agent_runtimes(id) ON DELETE CASCADE,
    agent_type text NOT NULL,
    status text NOT NULL,
    basic_available boolean,
    agent_compatible boolean,
    test_log_compare_compatible boolean,
    checks jsonb NOT NULL DEFAULT '[]'::jsonb,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_code text,
    message text,
    started_at timestamptz,
    finished_at timestamptz,
    duration_ms bigint,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT model_profile_agent_probe_results_status_chk
        CHECK (status IN ('SUCCESS', 'FAILED', 'TIMEOUT')),
    CONSTRAINT model_profile_agent_probe_results_agent_type_chk
        CHECK (agent_type IN ('CODEX', 'DEEPSEEK_HARNESS', 'OPENCODE'))
);

CREATE INDEX IF NOT EXISTS model_profile_agent_probe_results_run_idx
    ON model_profile_agent_probe_results(run_id);

CREATE INDEX IF NOT EXISTS model_profile_agent_probe_results_profile_runtime_created_idx
    ON model_profile_agent_probe_results(model_profile_id, agent_runtime_id, created_at DESC);

CREATE INDEX IF NOT EXISTS model_profile_agent_probe_results_profile_status_idx
    ON model_profile_agent_probe_results(model_profile_id, status);
