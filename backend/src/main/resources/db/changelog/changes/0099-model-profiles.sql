--liquibase formatted sql

--changeset rvport:0099-model-profiles
CREATE TABLE IF NOT EXISTS model_profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    enabled boolean NOT NULL DEFAULT true,
    executable_path text NOT NULL DEFAULT 'codex',
    model_provider_type text NOT NULL,
    base_url text,
    model text,
    wire_api text NOT NULL,
    api_key_encrypted text,
    timeout_seconds integer NOT NULL DEFAULT 30,
    max_runtime_seconds integer NOT NULL DEFAULT 1800,
    last_test_status text,
    last_test_message text,
    last_tested_at timestamptz,
    created_by uuid REFERENCES users(id),
    updated_by uuid REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT model_profiles_provider_type_chk CHECK (model_provider_type IN ('OPENAI_COMPATIBLE')),
    CONSTRAINT model_profiles_wire_api_chk CHECK (wire_api IN ('RESPONSES', 'CHAT')),
    CONSTRAINT model_profiles_test_status_chk CHECK (last_test_status IS NULL OR last_test_status IN ('SUCCESS', 'FAILED')),
    CONSTRAINT model_profiles_timeout_chk CHECK (timeout_seconds BETWEEN 1 AND 600),
    CONSTRAINT model_profiles_max_runtime_chk CHECK (max_runtime_seconds BETWEEN 10 AND 86400)
);

CREATE UNIQUE INDEX IF NOT EXISTS model_profiles_name_uidx
    ON model_profiles (lower(name));

CREATE INDEX IF NOT EXISTS model_profiles_enabled_idx
    ON model_profiles (enabled);

CREATE INDEX IF NOT EXISTS model_profiles_last_tested_at_idx
    ON model_profiles (last_tested_at DESC);

CREATE TABLE IF NOT EXISTS model_stage_assignments (
    stage text PRIMARY KEY,
    model_profile_id uuid NOT NULL REFERENCES model_profiles(id),
    updated_by uuid REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT model_stage_assignments_stage_chk CHECK (stage IN ('TEST_LOG_COMPARE'))
);

CREATE INDEX IF NOT EXISTS model_stage_assignments_profile_idx
    ON model_stage_assignments (model_profile_id);

INSERT INTO model_profiles (
    name,
    enabled,
    executable_path,
    model_provider_type,
    base_url,
    model,
    wire_api,
    api_key_encrypted,
    timeout_seconds,
    max_runtime_seconds,
    last_test_status,
    last_test_message,
    last_tested_at,
    updated_by
)
SELECT
    '默认 Codex Provider',
    COALESCE((SELECT config_value::boolean FROM system_configs WHERE namespace = 'codex-provider' AND config_key = 'enabled' AND encrypted = false), false),
    COALESCE((SELECT NULLIF(config_value, '') FROM system_configs WHERE namespace = 'codex-provider' AND config_key = 'executablePath' AND encrypted = false), 'codex'),
    COALESCE((SELECT NULLIF(config_value, '') FROM system_configs WHERE namespace = 'codex-provider' AND config_key = 'modelProviderType' AND encrypted = false), 'OPENAI_COMPATIBLE'),
    (SELECT NULLIF(config_value, '') FROM system_configs WHERE namespace = 'codex-provider' AND config_key = 'baseUrl' AND encrypted = false),
    (SELECT NULLIF(config_value, '') FROM system_configs WHERE namespace = 'codex-provider' AND config_key = 'model' AND encrypted = false),
    COALESCE((SELECT NULLIF(config_value, '') FROM system_configs WHERE namespace = 'codex-provider' AND config_key = 'wireApi' AND encrypted = false), 'RESPONSES'),
    (SELECT config_value FROM system_configs WHERE namespace = 'codex-provider' AND config_key = 'apiKey' AND encrypted = true),
    COALESCE((SELECT config_value::integer FROM system_configs WHERE namespace = 'codex-provider' AND config_key = 'timeoutSeconds' AND encrypted = false), 30),
    COALESCE((SELECT config_value::integer FROM system_configs WHERE namespace = 'codex-provider' AND config_key = 'maxRuntimeSeconds' AND encrypted = false), 1800),
    (SELECT NULLIF(config_value, '') FROM system_configs WHERE namespace = 'codex-provider' AND config_key = 'lastTestStatus' AND encrypted = false),
    (SELECT NULLIF(config_value, '') FROM system_configs WHERE namespace = 'codex-provider' AND config_key = 'lastTestMessage' AND encrypted = false),
    (SELECT config_value::timestamptz FROM system_configs WHERE namespace = 'codex-provider' AND config_key = 'lastTestedAt' AND encrypted = false AND NULLIF(config_value, '') IS NOT NULL),
    (SELECT updated_by FROM system_configs WHERE namespace = 'codex-provider' ORDER BY updated_at DESC NULLS LAST, created_at DESC LIMIT 1)
WHERE EXISTS (SELECT 1 FROM system_configs WHERE namespace = 'codex-provider')
  AND NOT EXISTS (SELECT 1 FROM model_profiles WHERE lower(name) = lower('默认 Codex Provider'));
