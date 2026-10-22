package cn.rvport.backend.project;

public enum ProjectStage {
    PROJECT_CREATED,
    SOURCE_IMPORTED,
    ENV_CONFIGURED,
    SCANNING,
    REPORT_GENERATED,
    WAITING_FIX,
    BUILD_PASSED,
    BUILD_FAILED,
    TEST_PASSED,
    TEST_FAILED,
    ARCHIVED
}
