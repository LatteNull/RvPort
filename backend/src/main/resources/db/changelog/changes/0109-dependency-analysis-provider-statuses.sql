--liquibase formatted sql

--changeset rvport:0111-dependency-analysis-provider-statuses
ALTER TABLE dependency_analysis_result_items
    DROP CONSTRAINT IF EXISTS dependency_analysis_result_items_match_status_chk;

ALTER TABLE dependency_analysis_result_items
    ADD CONSTRAINT dependency_analysis_result_items_match_status_chk CHECK (target_match_status IN (
        'SAME_MAJOR',
        'TARGET_NEWER',
        'TARGET_OLDER',
        'TARGET_PACKAGE_AVAILABLE_SOURCE_UNOWNED',
        'NO_TARGET_VERSION_FOUND',
        'TARGET_INSTALLED',
        'REPO_AVAILABLE',
        'PROVIDES_MATCH',
        'VERSION_MISMATCH',
        'SOURCE_BUILD_REQUIRED',
        'MISSING',
        'MANUAL_CONFIRM_REQUIRED'
    ));
