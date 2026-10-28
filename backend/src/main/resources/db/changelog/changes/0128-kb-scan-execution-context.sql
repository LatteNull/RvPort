--liquibase formatted sql

--changeset rvport:0128-kb-scan-execution-context
ALTER TABLE kb_scan_runs
    ADD COLUMN source_environment_id uuid REFERENCES environments(id),
    ADD COLUMN runtime_environment_version bigint,
    ADD COLUMN build_run_id uuid REFERENCES build_runs(id),
    ADD CONSTRAINT kb_scan_execution_context_complete_chk CHECK (
        (source_environment_id IS NULL AND runtime_environment_version IS NULL AND build_run_id IS NULL)
        OR (source_environment_id IS NOT NULL AND runtime_environment_version IS NOT NULL
            AND runtime_environment_version >= 0 AND build_run_id IS NOT NULL)
    );
CREATE INDEX kb_scan_runs_execution_context_idx ON kb_scan_runs
    (project_id, source_revision_id, source_environment_id, runtime_environment_version, build_run_id);

-- 创建扫描与上游上下文写入共用项目锁，防止校验后插入新构建的幻读。
--changeset rvport:0128-kb-context-lock-function splitStatements:false
CREATE FUNCTION lock_kb_execution_context() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended('rvport-kb-context:' ||
        CASE WHEN TG_OP = 'DELETE' THEN OLD.project_id ELSE NEW.project_id END::text, 0));
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$;

--changeset rvport:0128-kb-context-lock-triggers
CREATE TRIGGER kb_context_build_lock BEFORE INSERT OR UPDATE OR DELETE ON build_runs
    FOR EACH ROW EXECUTE FUNCTION lock_kb_execution_context();
CREATE TRIGGER kb_context_runtime_lock BEFORE INSERT OR UPDATE OR DELETE ON project_runtime_environments
    FOR EACH ROW EXECUTE FUNCTION lock_kb_execution_context();
CREATE TRIGGER kb_context_source_lock BEFORE INSERT OR UPDATE OR DELETE ON source_revisions
    FOR EACH ROW EXECUTE FUNCTION lock_kb_execution_context();
