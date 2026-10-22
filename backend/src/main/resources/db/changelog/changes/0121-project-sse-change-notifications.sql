--liquibase formatted sql

--changeset rvport:0121-project-sse-change-notifications
ALTER TABLE tasks
    ADD COLUMN stage_id text,
    ADD COLUMN resource_type text,
    ADD COLUMN resource_id uuid,
    ADD COLUMN resource_mode text,
    ADD COLUMN environment_role text;

ALTER TABLE task_events
    ALTER COLUMN task_id DROP NOT NULL,
    ADD COLUMN stage_id text,
    ADD COLUMN resource jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN changed_fields jsonb NOT NULL DEFAULT '[]'::jsonb;

CREATE INDEX task_events_event_type_idx ON task_events (event_type);
CREATE INDEX task_events_stage_id_idx ON task_events (stage_id);
CREATE INDEX tasks_stage_id_idx ON tasks (stage_id);
