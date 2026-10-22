--liquibase formatted sql

--changeset rvport:0058-system-configs
CREATE TABLE system_configs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    namespace text NOT NULL,
    config_key text NOT NULL,
    config_value text,
    value_type text NOT NULL,
    encrypted boolean NOT NULL DEFAULT false,
    description text,
    updated_by uuid REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz,
    CONSTRAINT system_configs_value_type_chk CHECK (value_type IN ('STRING', 'NUMBER', 'BOOLEAN', 'JSON', 'SECRET')),
    CONSTRAINT system_configs_namespace_key_uidx UNIQUE (namespace, config_key)
);

CREATE INDEX system_configs_namespace_idx ON system_configs (namespace);
CREATE INDEX system_configs_updated_by_idx ON system_configs (updated_by);

--changeset rvport:0058-user-action-tokens
CREATE TABLE user_action_tokens (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id),
    token_type text NOT NULL,
    token_hash text NOT NULL,
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz,
    created_by uuid REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT user_action_tokens_type_chk CHECK (token_type IN ('INVITATION', 'PASSWORD_RESET'))
);

CREATE UNIQUE INDEX user_action_tokens_hash_uidx ON user_action_tokens (token_hash);
CREATE INDEX user_action_tokens_user_type_consumed_idx ON user_action_tokens (user_id, token_type, consumed_at);
CREATE INDEX user_action_tokens_expires_at_idx ON user_action_tokens (expires_at);
CREATE INDEX user_action_tokens_created_by_idx ON user_action_tokens (created_by);
