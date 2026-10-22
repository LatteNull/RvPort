-- liquibase formatted sql

-- changeset rvport:0117-worker-instances
CREATE TABLE IF NOT EXISTS worker_instances (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    instance_id text NOT NULL UNIQUE,
    hostname text,
    process_id bigint,
    app_version text,
    status text NOT NULL DEFAULT 'ONLINE',
    concurrency_limit integer NOT NULL DEFAULT 1,
    active_concurrency integer NOT NULL DEFAULT 0,
    active_task_count integer NOT NULL DEFAULT 0,
    started_at timestamptz NOT NULL DEFAULT now(),
    last_heartbeat_at timestamptz NOT NULL DEFAULT now(),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT worker_instances_status_chk CHECK (status IN ('ONLINE', 'OFFLINE')),
    CONSTRAINT worker_instances_concurrency_limit_chk CHECK (concurrency_limit >= 0),
    CONSTRAINT worker_instances_active_concurrency_chk CHECK (active_concurrency >= 0),
    CONSTRAINT worker_instances_active_task_count_chk CHECK (active_task_count >= 0)
);

CREATE INDEX IF NOT EXISTS idx_worker_instances_last_heartbeat
    ON worker_instances (last_heartbeat_at DESC);

CREATE INDEX IF NOT EXISTS idx_worker_instances_hostname
    ON worker_instances (hostname);
