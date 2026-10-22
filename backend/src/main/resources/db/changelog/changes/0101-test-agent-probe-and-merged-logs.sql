--liquibase formatted sql

--changeset rvport:0101-test-agent-probe-and-merged-logs
ALTER TABLE model_profiles
    ADD COLUMN IF NOT EXISTS last_test_agent_type text,
    ADD COLUMN IF NOT EXISTS last_test_basic_available boolean,
    ADD COLUMN IF NOT EXISTS last_test_agent_compatible boolean,
    ADD COLUMN IF NOT EXISTS last_test_compare_compatible boolean,
    ADD COLUMN IF NOT EXISTS last_test_details jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE test_runs
    ADD COLUMN IF NOT EXISTS combined_log_id uuid REFERENCES task_logs(id);

ALTER TABLE test_comparison_runs
    ADD COLUMN IF NOT EXISTS source_test_stats jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS target_test_stats jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS model_profiles_last_test_agent_type_idx
    ON model_profiles(last_test_agent_type);

CREATE INDEX IF NOT EXISTS test_runs_combined_log_idx
    ON test_runs(combined_log_id);
