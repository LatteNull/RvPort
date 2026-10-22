-- liquibase formatted sql

-- changeset rvport:0122-worker-cleanup-indexes
CREATE INDEX IF NOT EXISTS idx_worker_instances_status_heartbeat
    ON worker_instances (status, last_heartbeat_at);

CREATE INDEX IF NOT EXISTS idx_task_runtime_handles_worker_non_terminal
    ON task_runtime_handles (worker_instance_id, status)
    WHERE status IN ('ACTIVE', 'CANCEL_REQUESTED', 'CANCELLING');
