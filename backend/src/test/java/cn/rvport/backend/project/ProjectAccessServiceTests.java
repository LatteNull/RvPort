package cn.rvport.backend.project;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.when;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.environment.EnvironmentRepository;
import cn.rvport.backend.environment.EnvironmentRole;
import cn.rvport.backend.environment.EnvironmentStatus;
import cn.rvport.backend.environment.EnvironmentView;
import cn.rvport.backend.source.SourceRepository;
import cn.rvport.backend.source.SourceRevisionType;
import cn.rvport.backend.source.SourceRevisionView;
import cn.rvport.backend.task.TaskLogRepository;
import cn.rvport.backend.task.TaskRepository;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.task.TaskView;
import java.time.OffsetDateTime;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class ProjectAccessServiceTests {

    private final ProjectRepository projectRepository = org.mockito.Mockito.mock(ProjectRepository.class);
    private final TaskRepository taskRepository = org.mockito.Mockito.mock(TaskRepository.class);
    private final EnvironmentRepository environmentRepository = org.mockito.Mockito.mock(EnvironmentRepository.class);
    private final SourceRepository sourceRepository = org.mockito.Mockito.mock(SourceRepository.class);
    private final TaskLogRepository taskLogRepository = org.mockito.Mockito.mock(TaskLogRepository.class);
    private final ProjectAccessService service = new ProjectAccessService(
            projectRepository,
            taskRepository,
            environmentRepository,
            sourceRepository,
            taskLogRepository
    );

    @Test
    void ownerCanAccessProjectAndSuperAdminCanAccessAnyProject() {
        UUID projectId = UUID.randomUUID();
        UUID ownerId = UUID.randomUUID();
        UUID adminId = UUID.randomUUID();
        ProjectView project = project(projectId, ownerId);
        when(projectRepository.findById(projectId)).thenReturn(Optional.of(project));

        assertThat(service.requireProjectAccess(projectId, ownerId, false)).isEqualTo(project);
        assertThat(service.requireProjectAccess(projectId, adminId, true)).isEqualTo(project);
    }

    @Test
    void normalUserCannotAccessOtherUsersProject() {
        UUID projectId = UUID.randomUUID();
        when(projectRepository.findById(projectId)).thenReturn(Optional.of(project(projectId, UUID.randomUUID())));

        assertThatThrownBy(() -> service.requireProjectAccess(projectId, UUID.randomUUID(), false))
                .isInstanceOf(ApiException.class)
                .hasMessage("项目不存在");
    }

    @Test
    void taskAccessUsesTaskProjectOwnership() {
        UUID ownerId = UUID.randomUUID();
        UUID projectId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        when(taskRepository.findById(taskId)).thenReturn(Optional.of(task(taskId, projectId, ownerId)));
        when(projectRepository.findById(projectId)).thenReturn(Optional.of(project(projectId, ownerId)));

        assertThat(service.requireTaskAccess(taskId, ownerId, false).id()).isEqualTo(taskId);

        assertThatThrownBy(() -> service.requireTaskAccess(taskId, UUID.randomUUID(), false))
                .isInstanceOf(ApiException.class)
                .hasMessage("项目不存在");
    }

    @Test
    void taskLogAccessRejectsLogOutsideTask() {
        UUID ownerId = UUID.randomUUID();
        UUID projectId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        UUID logId = UUID.randomUUID();
        when(taskRepository.findById(taskId)).thenReturn(Optional.of(task(taskId, projectId, ownerId)));
        when(projectRepository.findById(projectId)).thenReturn(Optional.of(project(projectId, ownerId)));
        when(taskLogRepository.findForTask(taskId, logId)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.requireTaskLogAccess(taskId, logId, ownerId, false))
                .isInstanceOf(ApiException.class)
                .hasMessage("任务日志不存在");
    }

    @Test
    void missingProjectsTasksAndEnvironmentsAreHiddenAsNotFound() {
        UUID actorId = UUID.randomUUID();
        UUID projectId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        UUID environmentId = UUID.randomUUID();

        assertCode(() -> service.requireProjectAccess(projectId, actorId, false), "PROJECT_NOT_FOUND");
        assertCode(() -> service.requireTaskAccess(taskId, actorId, false), "TASK_NOT_FOUND");
        assertCode(() -> service.requireEnvironmentAccess(environmentId, actorId, false), "ENVIRONMENT_NOT_FOUND");
    }

    @Test
    void environmentAndSourceRevisionAccessRequireMatchingProject() {
        UUID ownerId = UUID.randomUUID();
        UUID projectId = UUID.randomUUID();
        UUID environmentId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        when(projectRepository.findById(projectId)).thenReturn(Optional.of(project(projectId, ownerId)));
        EnvironmentView environment = environment(environmentId, projectId, ownerId);
        SourceRevisionView revision = revision(revisionId, projectId, ownerId);
        when(environmentRepository.findById(environmentId)).thenReturn(Optional.of(environment));
        when(sourceRepository.findById(revisionId)).thenReturn(Optional.of(revision));

        assertThat(service.requireEnvironmentAccess(environmentId, ownerId, false)).isEqualTo(environment);
        assertThat(service.requireSourceRevisionAccess(projectId, revisionId, ownerId, false)).isEqualTo(revision);

        UUID foreignRevisionId = UUID.randomUUID();
        when(sourceRepository.findById(foreignRevisionId))
                .thenReturn(Optional.of(revision(foreignRevisionId, UUID.randomUUID(), ownerId)));
        assertCode(() -> service.requireSourceRevisionAccess(projectId, foreignRevisionId, ownerId, false),
                "SOURCE_REVISION_NOT_FOUND");
        assertCode(() -> service.requireSourceRevisionAccess(projectId, UUID.randomUUID(), ownerId, false),
                "SOURCE_REVISION_NOT_FOUND");
    }

    @Test
    void taskLogAccessAcceptsLogOwnedByTask() {
        UUID ownerId = UUID.randomUUID();
        UUID projectId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        UUID logId = UUID.randomUUID();
        when(taskRepository.findById(taskId)).thenReturn(Optional.of(task(taskId, projectId, ownerId)));
        when(projectRepository.findById(projectId)).thenReturn(Optional.of(project(projectId, ownerId)));
        when(taskLogRepository.findForTask(taskId, logId)).thenReturn(Optional.of(
                new cn.rvport.backend.jooq.tables.records.TaskLogsRecord()));

        service.requireTaskLogAccess(taskId, logId, ownerId, false);
    }

    private void assertCode(org.assertj.core.api.ThrowableAssert.ThrowingCallable action, String code) {
        assertThatThrownBy(action).isInstanceOfSatisfying(ApiException.class,
                failure -> assertThat(failure.code()).isEqualTo(code));
    }

    private EnvironmentView environment(UUID id, UUID projectId, UUID createdBy) {
        return new EnvironmentView(id, projectId, "env", EnvironmentRole.SOURCE_X86, "x86_64", "localhost",
                22, "root", UUID.randomUUID(), null, "/tmp", EnvironmentStatus.AVAILABLE, true, 1L,
                null, null, createdBy, OffsetDateTime.now(), OffsetDateTime.now());
    }

    private SourceRevisionView revision(UUID id, UUID projectId, UUID createdBy) {
        return new SourceRevisionView(id, projectId, SourceRevisionType.GIT, "v1", null,
                "https://example.com/repo.git", "main", "abc", null, null, null, true, createdBy,
                OffsetDateTime.now());
    }

    private ProjectView project(UUID projectId, UUID createdBy) {
        return new ProjectView(
                projectId,
                "demo",
                null,
                "x86_64",
                "riscv64",
                ProjectStage.PROJECT_CREATED,
                ProjectStatus.ACTIVE,
                null,
                createdBy,
                OffsetDateTime.now(),
                null
        );
    }

    private TaskView task(UUID taskId, UUID projectId, UUID createdBy) {
        return new TaskView(
                taskId,
                projectId,
                "KB_SCAN",
                TaskStatus.PENDING,
                0,
                "开始扫描",
                createdBy,
                OffsetDateTime.now(),
                null,
                null,
                null,
                300,
                null,
                null,
                0
        );
    }
}
