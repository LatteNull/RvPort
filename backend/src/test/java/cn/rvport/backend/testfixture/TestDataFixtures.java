package cn.rvport.backend.testfixture;

import cn.rvport.backend.artifact.StoredArtifactOwnerType;
import cn.rvport.backend.artifact.StoredArtifactView;
import cn.rvport.backend.environment.EnvironmentRole;
import cn.rvport.backend.environment.EnvironmentStatus;
import cn.rvport.backend.environment.EnvironmentView;
import cn.rvport.backend.project.ProjectSourceInputType;
import cn.rvport.backend.project.ProjectStage;
import cn.rvport.backend.project.ProjectStatus;
import cn.rvport.backend.project.ProjectView;
import cn.rvport.backend.source.SourceRevisionType;
import cn.rvport.backend.source.SourceRevisionView;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.task.TaskView;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.Map;
import java.util.UUID;

public final class TestDataFixtures {

    public static final UUID USER_ID = UUID.fromString("00000000-0000-0000-0000-000000000001");
    public static final UUID PROJECT_ID = UUID.fromString("00000000-0000-0000-0000-000000000002");
    public static final UUID TASK_ID = UUID.fromString("00000000-0000-0000-0000-000000000003");
    public static final UUID ENVIRONMENT_ID = UUID.fromString("00000000-0000-0000-0000-000000000004");
    public static final UUID SOURCE_REVISION_ID = UUID.fromString("00000000-0000-0000-0000-000000000005");
    public static final UUID ARTIFACT_ID = UUID.fromString("00000000-0000-0000-0000-000000000006");
    public static final OffsetDateTime NOW = OffsetDateTime.of(2026, 9, 11, 12, 0, 0, 0, ZoneOffset.UTC);

    private TestDataFixtures() {
    }

    public static ProjectView project() {
        return new ProjectView(PROJECT_ID, "test-project", "description", "x86_64", "riscv64",
                ProjectStage.PROJECT_CREATED, ProjectStatus.ACTIVE, ProjectSourceInputType.GIT,
                USER_ID, NOW, NOW);
    }

    public static TaskView task() {
        return new TaskView(TASK_ID, PROJECT_ID, "KB_SCAN", TaskStatus.RUNNING, 50, "running",
                USER_ID, NOW, NOW, NOW, null, 1800, null, null, 0,
                "KB_SCAN", "KB_SCAN_RUN", TASK_ID, "DEFAULT", "TARGET_RISCV");
    }

    public static EnvironmentView environment() {
        return new EnvironmentView(ENVIRONMENT_ID, PROJECT_ID, "riscv", EnvironmentRole.TARGET_RISCV,
                "riscv64", "target.example", 22, "root", null, null, "/tmp/rvport",
                EnvironmentStatus.AVAILABLE, true, 2, NOW, NOW, USER_ID, NOW, NOW);
    }

    public static SourceRevisionView sourceRevision() {
        return new SourceRevisionView(SOURCE_REVISION_ID, PROJECT_ID, SourceRevisionType.GIT, "v1",
                "https://example/repository", "https://example/repository.git", "main", "abc123",
                null, "/tmp/source", "initial", true, USER_ID, NOW);
    }

    public static StoredArtifactView artifact() {
        return new StoredArtifactView(ARTIFACT_ID, PROJECT_ID, TASK_ID,
                StoredArtifactOwnerType.KB_SCAN, TASK_ID, "REPORT_JSON", "artifacts",
                "projects/test/report.json", "application/json", 128, "sha256",
                Map.of("findings", 3), NOW);
    }
}
