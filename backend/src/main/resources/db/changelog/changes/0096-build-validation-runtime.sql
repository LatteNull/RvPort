-- liquibase formatted sql

-- changeset rvport:0096-build-validation-runtime
ALTER TABLE build_runs
    ADD COLUMN source_deploy_run_id uuid,
    ADD COLUMN script_payload_id uuid,
    ADD COLUMN script_sha256 varchar(64),
    ADD COLUMN created_at timestamptz NOT NULL DEFAULT now();

ALTER TABLE build_runs
    ADD CONSTRAINT build_runs_source_deploy_run_id_fkey
        FOREIGN KEY (source_deploy_run_id) REFERENCES source_deploy_runs(id),
    ADD CONSTRAINT build_runs_script_payload_id_fkey
        FOREIGN KEY (script_payload_id) REFERENCES task_script_payloads(id),
    ADD CONSTRAINT build_runs_script_sha256_chk
        CHECK (script_sha256 IS NULL OR script_sha256 ~ '^[0-9a-f]{64}$');

CREATE INDEX build_runs_source_deploy_run_idx ON build_runs (source_deploy_run_id);
CREATE INDEX build_runs_status_started_idx ON build_runs (status, started_at DESC);
CREATE INDEX build_runs_project_created_idx ON build_runs (project_id, created_at DESC);
