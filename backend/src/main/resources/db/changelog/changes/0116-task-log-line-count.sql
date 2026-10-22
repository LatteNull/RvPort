-- liquibase formatted sql

-- changeset rvport:0116-task-log-line-count splitStatements:false
ALTER TABLE task_logs
    ADD COLUMN IF NOT EXISTS line_count bigint;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'task_logs_line_count_chk'
    ) THEN
        ALTER TABLE task_logs
            ADD CONSTRAINT task_logs_line_count_chk CHECK (line_count IS NULL OR line_count >= 0);
    END IF;
END $$;
