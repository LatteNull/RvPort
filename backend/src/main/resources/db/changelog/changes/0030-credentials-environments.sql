--liquibase formatted sql

--changeset rvport:0030-credentials
CREATE TABLE credentials (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid REFERENCES projects(id),
    owner_user_id uuid NOT NULL REFERENCES users(id),
    kind text NOT NULL,
    name text NOT NULL,
    encrypted_payload bytea NOT NULL,
    masked_summary text,
    kms_key_version text NOT NULL,
    status text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz,
    CONSTRAINT credentials_kind_chk CHECK (kind IN ('SSH_PASSWORD', 'SSH_KEY', 'GIT_PASSWORD', 'GIT_TOKEN')),
    CONSTRAINT credentials_status_chk CHECK (status IN ('ACTIVE', 'DISABLED', 'ROTATED'))
);

CREATE INDEX credentials_project_idx ON credentials (project_id);
CREATE INDEX credentials_owner_user_idx ON credentials (owner_user_id);
CREATE INDEX credentials_kind_idx ON credentials (kind);

--changeset rvport:0031-environments
CREATE TABLE environments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id),
    name text NOT NULL,
    role text NOT NULL,
    arch text NOT NULL,
    host text NOT NULL,
    ssh_port integer NOT NULL DEFAULT 22,
    username text NOT NULL,
    credential_id uuid NOT NULL REFERENCES credentials(id),
    working_directory text,
    status text NOT NULL,
    enabled boolean NOT NULL DEFAULT true,
    last_connected_at timestamptz,
    last_collected_at timestamptz,
    created_by uuid NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz,
    CONSTRAINT environments_role_chk CHECK (role IN ('SOURCE_X86', 'TARGET_RISCV', 'GENERAL_EXECUTION')),
    CONSTRAINT environments_ssh_port_chk CHECK (ssh_port BETWEEN 1 AND 65535),
    CONSTRAINT environments_status_chk CHECK (status IN ('UNKNOWN', 'AVAILABLE', 'UNAVAILABLE', 'DISABLED'))
);

CREATE INDEX environments_project_role_idx ON environments (project_id, role);
CREATE INDEX environments_project_enabled_idx ON environments (project_id, enabled);
CREATE INDEX environments_status_idx ON environments (status);
CREATE INDEX environments_credential_idx ON environments (credential_id);

--changeset rvport:0032-environment-snapshots
CREATE TABLE environment_snapshots (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    environment_id uuid NOT NULL REFERENCES environments(id),
    project_id uuid NOT NULL REFERENCES projects(id),
    task_id uuid NOT NULL,
    os_name text,
    os_version text,
    kernel_version text,
    arch text,
    package_manager text,
    repo_summary jsonb,
    tool_versions jsonb,
    raw_snapshot jsonb,
    status text NOT NULL,
    collected_at timestamptz NOT NULL,
    CONSTRAINT environment_snapshots_status_chk CHECK (status IN ('PENDING', 'QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'TIMEOUT'))
);

CREATE INDEX environment_snapshots_environment_collected_idx ON environment_snapshots (environment_id, collected_at DESC);
CREATE INDEX environment_snapshots_project_collected_idx ON environment_snapshots (project_id, collected_at DESC);

--changeset rvport:0033-environment-components
CREATE TABLE environment_components (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id uuid NOT NULL REFERENCES environment_snapshots(id),
    project_id uuid NOT NULL REFERENCES projects(id),
    name text NOT NULL,
    version text,
    component_type text NOT NULL,
    arch text,
    path text,
    source text,
    metadata jsonb,
    CONSTRAINT environment_components_type_chk CHECK (component_type IN ('PACKAGE', 'LIBRARY', 'TOOL', 'NATIVE_FILE'))
);

CREATE INDEX environment_components_snapshot_idx ON environment_components (snapshot_id);
CREATE INDEX environment_components_project_name_idx ON environment_components (project_id, name);
CREATE INDEX environment_components_arch_idx ON environment_components (arch);

--changeset rvport:0034-environment-jump-host
ALTER TABLE environments
    ADD COLUMN jump_host_environment_id uuid,
    ADD CONSTRAINT environments_jump_host_fk FOREIGN KEY (jump_host_environment_id) REFERENCES environments(id),
    ADD CONSTRAINT environments_jump_host_not_self_chk CHECK (jump_host_environment_id IS NULL OR jump_host_environment_id <> id);

CREATE INDEX environments_jump_host_idx ON environments (jump_host_environment_id);
