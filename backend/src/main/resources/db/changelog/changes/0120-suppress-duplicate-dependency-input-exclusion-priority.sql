-- Re-run current dependency input de-duplication with EXCLUDED priority.
-- This preserves manual exclusions when a duplicate confirmed/candidate ref exists.
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
                    WHEN 'EXCLUDED' THEN 0
                    WHEN 'CONFIRMED' THEN 1
                    WHEN 'CANDIDATE' THEN 2
                    ELSE 3
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
