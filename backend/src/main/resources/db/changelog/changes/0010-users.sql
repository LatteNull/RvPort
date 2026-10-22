--liquibase formatted sql

--changeset rvport:0010-users
CREATE TABLE users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    username text NOT NULL,
    display_name text,
    email text,
    password_hash text NOT NULL,
    is_super_admin boolean NOT NULL DEFAULT false,
    must_change_password boolean NOT NULL DEFAULT false,
    status text NOT NULL,
    last_login_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz,
    CONSTRAINT users_status_chk CHECK (status IN ('ACTIVE', 'DISABLED'))
);

CREATE UNIQUE INDEX users_username_uidx ON users (username);
CREATE UNIQUE INDEX users_email_uidx ON users (email) WHERE email IS NOT NULL;
CREATE INDEX users_status_idx ON users (status);
CREATE INDEX users_super_admin_idx ON users (is_super_admin) WHERE is_super_admin = true;

--changeset rvport:0011-seed-default-admin
INSERT INTO users (
    username,
    display_name,
    password_hash,
    is_super_admin,
    must_change_password,
    status,
    created_at
) VALUES (
    'admin',
    'Admin',
    '$argon2id$v=19$m=16384,t=3,p=1$0DDNzknNExGzVkNXJD4Odw$+gkl+5vHj+GD7vrvyzya/xrsKHHuBf++1PWshNa6O04',
    true,
    true,
    'ACTIVE',
    now()
) ON CONFLICT (username) DO NOTHING;
