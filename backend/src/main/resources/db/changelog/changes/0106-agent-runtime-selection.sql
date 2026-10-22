--liquibase formatted sql

--changeset rvport:0106-agent-runtime-selection
CREATE TABLE IF NOT EXISTS agent_runtimes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_type text NOT NULL,
    name text NOT NULL,
    enabled boolean NOT NULL DEFAULT true,
    executable_path text NOT NULL,
    default_args jsonb NOT NULL DEFAULT '[]'::jsonb,
    config jsonb NOT NULL DEFAULT '{}'::jsonb,
    last_probe_status text,
    last_probe_message text,
    last_probe_details jsonb NOT NULL DEFAULT '{}'::jsonb,
    last_probe_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT agent_runtimes_type_chk CHECK (agent_type IN ('CODEX', 'DEEPSEEK_HARNESS', 'OPENCODE')),
    CONSTRAINT agent_runtimes_probe_status_chk CHECK (last_probe_status IS NULL OR last_probe_status IN ('SUCCESS', 'FAILED'))
);

CREATE UNIQUE INDEX IF NOT EXISTS agent_runtimes_type_uidx
    ON agent_runtimes (agent_type);

CREATE UNIQUE INDEX IF NOT EXISTS agent_runtimes_name_uidx
    ON agent_runtimes (lower(name));

CREATE INDEX IF NOT EXISTS agent_runtimes_enabled_idx
    ON agent_runtimes (enabled);

INSERT INTO agent_runtimes (agent_type, name, enabled, executable_path, default_args, config)
VALUES
    ('CODEX', 'Codex', true, COALESCE((SELECT executable_path FROM model_profiles ORDER BY created_at ASC LIMIT 1), 'codex'), '[]'::jsonb, '{}'::jsonb),
    ('DEEPSEEK_HARNESS', 'DeepSeek Harness', true, 'dsh', '[]'::jsonb, '{}'::jsonb),
    ('OPENCODE', 'OpenCode', true, 'opencode', '[]'::jsonb, '{}'::jsonb)
ON CONFLICT (agent_type) DO UPDATE
SET
    name = EXCLUDED.name,
    updated_at = now();

ALTER TABLE model_stage_assignments
    ADD COLUMN IF NOT EXISTS agent_runtime_id uuid;

UPDATE model_stage_assignments
SET agent_runtime_id = (SELECT id FROM agent_runtimes WHERE agent_type = 'CODEX')
WHERE agent_runtime_id IS NULL;

ALTER TABLE model_stage_assignments
    ADD CONSTRAINT model_stage_assignments_agent_runtime_fk
        FOREIGN KEY (agent_runtime_id) REFERENCES agent_runtimes(id);

ALTER TABLE model_stage_assignments
    ALTER COLUMN agent_runtime_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS model_stage_assignments_agent_runtime_idx
    ON model_stage_assignments (agent_runtime_id);
