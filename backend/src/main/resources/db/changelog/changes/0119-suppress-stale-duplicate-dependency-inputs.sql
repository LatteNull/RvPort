-- 清理当前迁移输入池中的过期依赖分析引用。
-- 注意：只处理 migration_input_refs，不修改历史 report_inputs 快照，也不删除 dependency_analysis_result_items 原始结果。
WITH latest_dependency_runs AS (
    SELECT DISTINCT ON (project_id, source_revision_id)
        id,
        project_id,
        source_revision_id
    FROM dependency_analysis_runs
    WHERE status = 'SUCCEEDED'
    ORDER BY project_id, source_revision_id, finished_at DESC NULLS LAST, created_at DESC, id DESC
),
stale_refs AS (
    SELECT mir.id
    FROM migration_input_refs mir
    JOIN dependency_analysis_result_items item
        ON item.id = mir.source_ref_id
    JOIN latest_dependency_runs latest
        ON latest.project_id = mir.project_id
        AND latest.source_revision_id = mir.source_revision_id
    WHERE mir.source_type = 'DEPENDENCY_RESULT'
      AND item.dependency_analysis_run_id <> latest.id
)
DELETE FROM migration_input_refs mir
WHERE mir.id IN (SELECT id FROM stale_refs);

-- 收敛同一当前输入池内的同语义依赖重复项，例如 build:gcc / execve:gcc 或重复 glibc。
WITH ranked_refs AS (
    SELECT
        mir.id,
        row_number() OVER (
            PARTITION BY
                mir.input_set_id,
                mir.source_type,
                lower(coalesce(nullif(mir.rule_id, ''), '')),
                lower(coalesce(nullif(mir.identity_path, ''), nullif(mir.identity_symbol, ''), nullif(mir.issue_title, '')))
            ORDER BY
                CASE mir.status
                    WHEN 'CONFIRMED' THEN 0
                    WHEN 'CANDIDATE' THEN 1
                    ELSE 2
                END,
                CASE split_part(upper(coalesce(mir.detected_level, 'INFO')), '/', 1)
                    WHEN 'CRITICAL' THEN 0
                    WHEN 'HIGH' THEN 1
                    WHEN 'MEDIUM' THEN 2
                    WHEN 'LOW' THEN 3
                    WHEN 'INFO' THEN 4
                    ELSE 5
                END,
                mir.updated_at DESC NULLS LAST,
                mir.created_at DESC,
                mir.id DESC
        ) AS rn
    FROM migration_input_refs mir
    WHERE mir.source_type = 'DEPENDENCY_RESULT'
      AND coalesce(nullif(mir.identity_path, ''), nullif(mir.identity_symbol, ''), nullif(mir.issue_title, '')) IS NOT NULL
)
DELETE FROM migration_input_refs mir
WHERE mir.id IN (
    SELECT id
    FROM ranked_refs
    WHERE rn > 1
);
