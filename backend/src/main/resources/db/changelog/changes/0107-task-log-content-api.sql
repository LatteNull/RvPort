-- liquibase formatted sql

-- changeset rvport:0107-task-log-content-api
ALTER TABLE build_runs
    ADD COLUMN combined_log_id uuid;

ALTER TABLE build_runs
    ADD CONSTRAINT build_runs_combined_log_id_fkey
        FOREIGN KEY (combined_log_id) REFERENCES task_logs(id);
