--liquibase formatted sql

--changeset rvport:0124-decouple-model-agent-compatibility
ALTER TABLE model_profile_agent_probe_results
    DROP COLUMN IF EXISTS test_log_compare_compatible,
    DROP COLUMN IF EXISTS kb_ai_extension_compatible;

ALTER TABLE model_profiles
    DROP COLUMN IF EXISTS last_test_compare_compatible;
