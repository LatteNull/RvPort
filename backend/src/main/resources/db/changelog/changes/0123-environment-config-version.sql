--liquibase formatted sql

--changeset rvport:0123-environment-config-version
ALTER TABLE environments
    ADD COLUMN IF NOT EXISTS config_version bigint NOT NULL DEFAULT 1;

ALTER TABLE environment_snapshots
    ADD COLUMN IF NOT EXISTS environment_config_version bigint;

UPDATE environment_snapshots snapshot
SET environment_config_version = environment.config_version
FROM environments environment
WHERE snapshot.environment_id = environment.id
  AND snapshot.environment_config_version IS NULL;

ALTER TABLE environment_snapshots
    ALTER COLUMN environment_config_version SET NOT NULL;

CREATE INDEX IF NOT EXISTS environment_snapshots_environment_config_collected_idx
    ON environment_snapshots(environment_id, environment_config_version, collected_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS environments_credential_config_idx
    ON environments(credential_id, config_version);

CREATE INDEX IF NOT EXISTS environments_jump_host_config_idx
    ON environments(jump_host_environment_id, config_version)
    WHERE jump_host_environment_id IS NOT NULL;
