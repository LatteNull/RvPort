--liquibase formatted sql

--changeset rvport:0112-dependency-analysis-provider-version-fields
ALTER TABLE dependency_analysis_result_items
    ADD COLUMN IF NOT EXISTS source_provider_package text,
    ADD COLUMN IF NOT EXISTS source_provider_version text,
    ADD COLUMN IF NOT EXISTS source_detected_version text,
    ADD COLUMN IF NOT EXISTS target_provider_package text,
    ADD COLUMN IF NOT EXISTS target_provider_version text,
    ADD COLUMN IF NOT EXISTS target_detected_version text,
    ADD COLUMN IF NOT EXISTS provider_version_status text,
    ADD COLUMN IF NOT EXISTS version_evidence_confidence text;

ALTER TABLE dependency_analysis_result_items
    DROP CONSTRAINT IF EXISTS dependency_analysis_result_items_provider_version_status_chk;

ALTER TABLE dependency_analysis_result_items
    ADD CONSTRAINT dependency_analysis_result_items_provider_version_status_chk CHECK (
        provider_version_status IS NULL OR provider_version_status IN (
            'SAME_MAJOR',
            'TARGET_NEWER',
            'TARGET_OLDER',
            'TARGET_PACKAGE_AVAILABLE_SOURCE_UNOWNED',
            'NO_TARGET_VERSION_FOUND',
            'UNKNOWN'
        )
    );

ALTER TABLE dependency_analysis_result_items
    DROP CONSTRAINT IF EXISTS dependency_analysis_result_items_version_evidence_confidence_chk;

ALTER TABLE dependency_analysis_result_items
    ADD CONSTRAINT dependency_analysis_result_items_version_evidence_confidence_chk CHECK (
        version_evidence_confidence IS NULL OR version_evidence_confidence IN (
            'PACKAGE_OWNER',
            'COMMAND_VERSION',
            'ELF_METADATA',
            'FILENAME',
            'STRINGS',
            'UNKNOWN'
        )
    );

CREATE INDEX IF NOT EXISTS dependency_analysis_items_project_revision_provider_status_idx
    ON dependency_analysis_result_items(project_id, source_revision_id, provider_version_status);

CREATE INDEX IF NOT EXISTS dependency_analysis_items_project_revision_source_provider_idx
    ON dependency_analysis_result_items(project_id, source_revision_id, source_provider_package);

CREATE INDEX IF NOT EXISTS dependency_analysis_items_project_revision_target_provider_idx
    ON dependency_analysis_result_items(project_id, source_revision_id, target_provider_package);
