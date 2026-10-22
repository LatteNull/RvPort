package cn.rvport.backend.source.deploy;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.audit.AuditLogService;
import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.environment.EnvironmentRepository;
import cn.rvport.backend.environment.EnvironmentRole;
import cn.rvport.backend.environment.EnvironmentStatus;
import cn.rvport.backend.environment.EnvironmentView;
import cn.rvport.backend.project.ProjectAccessService;
import cn.rvport.backend.project.runtime.ProjectRuntimeEnvironmentService;
import cn.rvport.backend.project.runtime.ProjectRuntimeEnvironmentView;
import cn.rvport.backend.source.SourceRepository;
import cn.rvport.backend.source.SourceRevisionType;
import cn.rvport.backend.source.SourceRevisionView;
import cn.rvport.backend.task.RvPortTaskTypes;
import cn.rvport.backend.task.TaskCreateCommand;
import cn.rvport.backend.task.TaskRepository;
import cn.rvport.backend.task.TaskResponse;
import cn.rvport.backend.task.TaskService;
import cn.rvport.backend.task.TaskStatus;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.jooq.JSONB;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class SourceDeployServiceTests {

    @TempDir
    Path tempDir;

    @Mock
    private SourceDeployRepository sourceDeployRepository;
    @Mock
    private SourceRepository sourceRepository;
    @Mock
    private EnvironmentRepository environmentRepository;
    @Mock
    private ProjectRuntimeEnvironmentService projectRuntimeEnvironmentService;
    @Mock
    private ProjectAccessService projectAccessService;
    @Mock
    private TaskService taskService;
    @Mock
    private TaskRepository taskRepository;
    @Mock
    private AuditLogService auditLogService;

    @Test
    void createsDeploymentsForSourceAndTargetEnvironments() throws Exception {
        SourceDeployService service = service();
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        SourceRevisionView revision = revision(projectId, tempDir);
        EnvironmentView x86 = environment(projectId, EnvironmentRole.SOURCE_X86, "/workspace/x86");
        EnvironmentView riscv = environment(projectId, EnvironmentRole.TARGET_RISCV, "/workspace/riscv");
        when(projectRuntimeEnvironmentService.requireComplete(projectId, actorId, false))
                .thenReturn(new ProjectRuntimeEnvironmentView(projectId, x86.id(), riscv.id(), 2L, actorId, null, null));
        when(sourceRepository.findById(revision.id())).thenReturn(Optional.of(revision));
        when(environmentRepository.findById(x86.id())).thenReturn(Optional.of(x86));
        when(environmentRepository.findById(riscv.id())).thenReturn(Optional.of(riscv));
        when(sourceDeployRepository.findReusable(projectId, revision.id(), x86.id(), 2L)).thenReturn(Optional.empty());
        when(sourceDeployRepository.findReusable(projectId, revision.id(), riscv.id(), 2L)).thenReturn(Optional.empty());
        when(taskService.create(any())).thenAnswer(invocation -> task(projectId, actorId, invocation.getArgument(0)));
        when(sourceDeployRepository.createPending(any(), eq(projectId), any(), eq(revision.id()), eq(x86.id()), eq(2L), eq("/workspace/x86/rvport-sources/" + revision.id()), eq(false)))
                .thenAnswer(invocation -> run(invocation.getArgument(0), projectId, invocation.getArgument(2), revision.id(), x86.id(), invocation.getArgument(6), TaskStatus.PENDING));
        when(sourceDeployRepository.createPending(any(), eq(projectId), any(), eq(revision.id()), eq(riscv.id()), eq(2L), eq("/workspace/riscv/rvport-sources/" + revision.id()), eq(false)))
                .thenAnswer(invocation -> run(invocation.getArgument(0), projectId, invocation.getArgument(2), revision.id(), riscv.id(), invocation.getArgument(6), TaskStatus.PENDING));

        SourceDeployCreateResponse response = service.create(
                projectId,
                new SourceDeployCreateRequest(revision.id(), null, false, 120),
                actorId,
                false,
                null
        );

        assertThat(response.deployments()).hasSize(2);
        assertThat(response.deployments()).extracting(SourceDeployResponse::environmentId)
                .containsExactly(x86.id(), riscv.id());
        verify(taskService).create(org.mockito.ArgumentMatchers.argThat(command ->
                command.type().equals(RvPortTaskTypes.SOURCE_DEPLOY)
                        && command.inputSnapshot().get("environmentId").equals(x86.id())
                        && !command.inputSnapshot().toString().contains(revision.workingCopyPath())
        ));
        verify(taskService).create(org.mockito.ArgumentMatchers.argThat(command ->
                command.type().equals(RvPortTaskTypes.SOURCE_DEPLOY)
                        && command.inputSnapshot().get("environmentId").equals(riscv.id())
        ));
    }

    @Test
    void reusesExistingDeploymentWhenForceIsFalse() throws Exception {
        SourceDeployService service = service();
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        SourceRevisionView revision = revision(projectId, tempDir);
        EnvironmentView environment = environment(projectId, EnvironmentRole.TARGET_RISCV, "/workspace");
        SourceDeployRunView existing = run(UUID.randomUUID(), projectId, UUID.randomUUID(), revision.id(), environment.id(),
                "/workspace/rvport-sources/" + revision.id(), TaskStatus.SUCCEEDED);
        EnvironmentView source = environment(projectId, EnvironmentRole.SOURCE_X86, "/source");
        when(projectRuntimeEnvironmentService.requireComplete(projectId, actorId, false))
                .thenReturn(new ProjectRuntimeEnvironmentView(projectId, source.id(), environment.id(), 2L, actorId, null, null));
        when(environmentRepository.findById(source.id())).thenReturn(Optional.of(source));
        when(sourceRepository.findById(revision.id())).thenReturn(Optional.of(revision));
        when(environmentRepository.findById(environment.id())).thenReturn(Optional.of(environment));
        when(sourceDeployRepository.findReusable(projectId, revision.id(), source.id(), 2L)).thenReturn(Optional.of(existing));
        when(sourceDeployRepository.findReusable(projectId, revision.id(), environment.id(), 2L)).thenReturn(Optional.of(existing));

        SourceDeployCreateResponse response = service.create(
                projectId,
                new SourceDeployCreateRequest(revision.id(), null, false, null),
                actorId,
                false,
                null
        );

        assertThat(response.deployments()).hasSize(2);
        verify(taskService, never()).create(any());
    }

    @Test
    void rejectsMissingWorkingDirectoryAndMissingWorkingCopyAsExceptions() throws Exception {
        SourceDeployService service = service();
        UUID projectId = UUID.randomUUID();
        SourceRevisionView revision = revision(projectId, tempDir);
        EnvironmentView noWorkdir = environment(projectId, EnvironmentRole.TARGET_RISCV, null);
        EnvironmentView source = environment(projectId, EnvironmentRole.SOURCE_X86, "/source");
        when(projectRuntimeEnvironmentService.requireComplete(eq(projectId), any(), eq(false)))
                .thenReturn(new ProjectRuntimeEnvironmentView(projectId, source.id(), noWorkdir.id(), 2L, UUID.randomUUID(), null, null));
        when(sourceRepository.findById(revision.id())).thenReturn(Optional.of(revision));
        when(environmentRepository.findById(source.id())).thenReturn(Optional.of(source));
        when(environmentRepository.findById(noWorkdir.id())).thenReturn(Optional.of(noWorkdir));
        when(sourceDeployRepository.findReusable(projectId, revision.id(), source.id(), 2L))
                .thenReturn(Optional.of(run(UUID.randomUUID(), projectId, UUID.randomUUID(), revision.id(), source.id(),
                        "/source/rvport-sources/" + revision.id(), TaskStatus.SUCCEEDED)));

        assertThatThrownBy(() -> service.create(projectId,
                new SourceDeployCreateRequest(revision.id(), null, false, null),
                UUID.randomUUID(), false, null))
                .isInstanceOf(ApiException.class)
                .extracting("code")
                .isEqualTo("ENVIRONMENT_WORKING_DIRECTORY_REQUIRED");

        SourceRevisionView missingCopy = new SourceRevisionView(
                UUID.randomUUID(), projectId, SourceRevisionType.ARCHIVE, "v1", "source.zip",
                null, null, null, null, tempDir.resolve("missing").toString(), null, true,
                UUID.randomUUID(), OffsetDateTime.now());
        when(sourceRepository.findById(missingCopy.id())).thenReturn(Optional.of(missingCopy));
        assertThatThrownBy(() -> service.create(projectId,
                new SourceDeployCreateRequest(missingCopy.id(), null, false, null),
                UUID.randomUUID(), false, null))
                .isInstanceOf(ApiException.class)
                .extracting("code")
                .isEqualTo("SOURCE_REVISION_WORKING_COPY_NOT_FOUND");
    }

    @Test
    void rejectsInvalidSortAsEdgeCase() {
        SourceDeployService service = service();
        UUID projectId = UUID.randomUUID();

        assertThatThrownBy(() -> service.list(projectId,
                new SourceDeployListRequest(1, 20, null, null, null, null, null, "remotePath", "desc"),
                UUID.randomUUID(), false))
                .isInstanceOf(ApiException.class)
                .extracting("code")
                .isEqualTo("SOURCE_DEPLOY_QUERY_INVALID");

        assertThatThrownBy(() -> service.list(projectId,
                new SourceDeployListRequest(1, 20, null, null, null, null, null, "status", "sideways"),
                UUID.randomUUID(), false))
                .isInstanceOf(ApiException.class)
                .extracting("code")
                .isEqualTo("SOURCE_DEPLOY_QUERY_INVALID");
    }

    @Test
    void listsGetsAndCancelsAccessibleDeployments() {
        SourceDeployService service = service();
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        SourceDeployRunView run = run(UUID.randomUUID(), projectId, taskId, UUID.randomUUID(), UUID.randomUUID(),
                "/workspace/source", TaskStatus.RUNNING);
        SourceDeployListRequest request = new SourceDeployListRequest(
                null, null, null, null, null, null, null, " status ", " ASC ");
        when(sourceDeployRepository.count(projectId, request)).thenReturn(1L);
        when(sourceDeployRepository.list(projectId, request)).thenReturn(List.of(run));
        when(sourceDeployRepository.findById(run.id())).thenReturn(Optional.of(run));
        when(projectRuntimeEnvironmentService.currentVersion(projectId)).thenReturn(2L);
        TaskResponse canceled = new TaskResponse(taskId, projectId, RvPortTaskTypes.SOURCE_DEPLOY,
                TaskStatus.CANCELLED, 0, "canceled", OffsetDateTime.now(), null, null, null, null, null, Map.of());
        when(taskService.cancel(taskId, actorId, false)).thenReturn(canceled);

        assertThat(service.list(projectId, request, actorId, false).items()).hasSize(1);
        assertThat(service.get(run.id(), actorId, false).id()).isEqualTo(run.id());
        assertThat(service.cancel(run.id(), actorId, false).status()).isEqualTo(TaskStatus.CANCELLED);
        verify(sourceDeployRepository).syncStatusByTask(taskId, TaskStatus.CANCELLED);
    }

    @Test
    void rejectsDeprecatedEnvironmentSelectionAndMissingOrForeignResources() throws Exception {
        SourceDeployService service = service();
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        SourceRevisionView revision = revision(projectId, tempDir);
        when(sourceRepository.findById(revision.id())).thenReturn(Optional.of(revision));

        assertThatThrownBy(() -> service.create(projectId,
                new SourceDeployCreateRequest(revision.id(), List.of(UUID.randomUUID()), false, null),
                actorId, false, null))
                .isInstanceOf(ApiException.class)
                .extracting("code").isEqualTo("SOURCE_DEPLOY_ENVIRONMENTS_DEPRECATED");

        UUID missingRevision = UUID.randomUUID();
        when(sourceRepository.findById(missingRevision)).thenReturn(Optional.empty());
        assertThatThrownBy(() -> service.create(projectId,
                new SourceDeployCreateRequest(missingRevision, null, false, null), actorId, false, null))
                .isInstanceOf(ApiException.class)
                .extracting("code").isEqualTo("SOURCE_REVISION_NOT_FOUND");

        SourceRevisionView foreign = revision(UUID.randomUUID(), tempDir);
        when(sourceRepository.findById(foreign.id())).thenReturn(Optional.of(foreign));
        assertThatThrownBy(() -> service.create(projectId,
                new SourceDeployCreateRequest(foreign.id(), null, false, null), actorId, false, null))
                .isInstanceOf(ApiException.class)
                .extracting("code").isEqualTo("SOURCE_REVISION_NOT_FOUND");

        UUID missingDeploy = UUID.randomUUID();
        when(sourceDeployRepository.findById(missingDeploy)).thenReturn(Optional.empty());
        assertThatThrownBy(() -> service.get(missingDeploy, actorId, false))
                .isInstanceOf(ApiException.class)
                .extracting("code").isEqualTo("SOURCE_DEPLOYMENT_NOT_FOUND");
    }

    @Test
    void forceDeploymentAcceptsExplicitEmptyEnvironmentListAndSkipsReuseLookup() throws Exception {
        SourceDeployService service = service();
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        SourceRevisionView revision = revision(projectId, tempDir);
        EnvironmentView source = environment(projectId, EnvironmentRole.SOURCE_X86, "/source/");
        EnvironmentView target = environment(projectId, EnvironmentRole.TARGET_RISCV, "/target\\");
        when(sourceRepository.findById(revision.id())).thenReturn(Optional.of(revision));
        when(projectRuntimeEnvironmentService.requireComplete(projectId, actorId, false))
                .thenReturn(new ProjectRuntimeEnvironmentView(projectId, source.id(), target.id(), 8L,
                        actorId, null, null));
        when(environmentRepository.findById(source.id())).thenReturn(Optional.of(source));
        when(environmentRepository.findById(target.id())).thenReturn(Optional.of(target));
        when(taskService.create(any())).thenAnswer(invocation -> task(projectId, actorId, invocation.getArgument(0)));
        when(sourceDeployRepository.createPending(any(), eq(projectId), any(), eq(revision.id()), any(),
                eq(8L), any(), eq(true))).thenAnswer(invocation -> run(invocation.getArgument(0), projectId,
                invocation.getArgument(2), revision.id(), invocation.getArgument(4), invocation.getArgument(6),
                TaskStatus.PENDING));

        SourceDeployCreateResponse response = service.create(projectId,
                new SourceDeployCreateRequest(revision.id(), List.of(), true, null), actorId, false, null);

        assertThat(response.deployments()).hasSize(2);
        verify(sourceDeployRepository, never()).findReusable(any(), any(), any(), any(Long.class));
        verify(taskService, org.mockito.Mockito.times(2)).create(org.mockito.ArgumentMatchers.argThat(command ->
                Boolean.TRUE.equals(command.inputSnapshot().get("force")) && command.timeoutSeconds() == 3600));
    }

    @Test
    void rejectsForeignDisabledAndBlankWorkingDirectoryEnvironments() throws Exception {
        SourceDeployService service = service();
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        SourceRevisionView revision = revision(projectId, tempDir);
        EnvironmentView foreign = environment(UUID.randomUUID(), EnvironmentRole.SOURCE_X86, "/work");
        EnvironmentView disabled = copyEnvironment(
                environment(projectId, EnvironmentRole.SOURCE_X86, "/work"), false, "/work");
        EnvironmentView blankDirectory = copyEnvironment(
                environment(projectId, EnvironmentRole.SOURCE_X86, "/work"), true, "  ");
        when(sourceRepository.findById(revision.id())).thenReturn(Optional.of(revision));
        when(projectRuntimeEnvironmentService.requireComplete(projectId, actorId, false))
                .thenReturn(runtime(projectId, actorId, foreign.id()), runtime(projectId, actorId, disabled.id()),
                        runtime(projectId, actorId, blankDirectory.id()));
        when(environmentRepository.findById(foreign.id())).thenReturn(Optional.of(foreign));
        when(environmentRepository.findById(disabled.id())).thenReturn(Optional.of(disabled));
        when(environmentRepository.findById(blankDirectory.id())).thenReturn(Optional.of(blankDirectory));

        assertCode(() -> service.create(projectId,
                new SourceDeployCreateRequest(revision.id(), null, false, null), actorId, false, null),
                "ENVIRONMENT_NOT_FOUND");
        assertCode(() -> service.create(projectId,
                new SourceDeployCreateRequest(revision.id(), null, false, null), actorId, false, null),
                "ENVIRONMENT_DISABLED");
        assertCode(() -> service.create(projectId,
                new SourceDeployCreateRequest(revision.id(), null, false, null), actorId, false, null),
                "ENVIRONMENT_WORKING_DIRECTORY_REQUIRED");
    }

    @Test
    void rejectsNullOrBlankWorkingCopyAndAcceptsBlankSortOptions() {
        SourceDeployService service = service();
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        SourceRevisionView base = new SourceRevisionView(UUID.randomUUID(), projectId, SourceRevisionType.ARCHIVE,
                "v1", "source.zip", null, null, null, null, null, null, true, actorId, OffsetDateTime.now());
        SourceRevisionView blank = new SourceRevisionView(UUID.randomUUID(), projectId, SourceRevisionType.ARCHIVE,
                "v2", "source.zip", null, null, null, null, "  ", null, true, actorId, OffsetDateTime.now());
        when(sourceRepository.findById(base.id())).thenReturn(Optional.of(base));
        when(sourceRepository.findById(blank.id())).thenReturn(Optional.of(blank));

        assertCode(() -> service.create(projectId,
                new SourceDeployCreateRequest(base.id(), null, false, null), actorId, false, null),
                "SOURCE_REVISION_WORKING_COPY_NOT_FOUND");
        assertCode(() -> service.create(projectId,
                new SourceDeployCreateRequest(blank.id(), null, false, null), actorId, false, null),
                "SOURCE_REVISION_WORKING_COPY_NOT_FOUND");

        for (SourceDeployListRequest request : List.of(
                new SourceDeployListRequest(null, null, null, null, null, null, null, null, null),
                new SourceDeployListRequest(null, null, null, null, null, null, null, " ", " "))) {
            when(sourceDeployRepository.count(projectId, request)).thenReturn(0L);
            when(sourceDeployRepository.list(projectId, request)).thenReturn(List.of());
            assertThat(service.list(projectId, request, actorId, false).items()).isEmpty();
        }
    }

    private void assertCode(org.assertj.core.api.ThrowableAssert.ThrowingCallable action, String code) {
        assertThatThrownBy(action).isInstanceOf(ApiException.class).extracting("code").isEqualTo(code);
    }

    private ProjectRuntimeEnvironmentView runtime(UUID projectId, UUID actorId, UUID sourceId) {
        return new ProjectRuntimeEnvironmentView(projectId, sourceId, UUID.randomUUID(), 1L, actorId, null, null);
    }

    private EnvironmentView copyEnvironment(EnvironmentView view, boolean enabled, String workingDirectory) {
        return new EnvironmentView(view.id(), view.projectId(), view.name(), view.role(), view.arch(), view.host(),
                view.sshPort(), view.username(), view.credentialId(), view.jumpHostEnvironmentId(), workingDirectory,
                enabled ? EnvironmentStatus.AVAILABLE : EnvironmentStatus.DISABLED, enabled, view.configVersion(),
                view.lastConnectedAt(), view.lastCollectedAt(), view.createdBy(), view.createdAt(), view.updatedAt());
    }

    private SourceDeployService service() {
        return new SourceDeployService(sourceDeployRepository, sourceRepository, environmentRepository,
                projectRuntimeEnvironmentService, projectAccessService, taskService, taskRepository, auditLogService, new ObjectMapper());
    }

    private SourceRevisionView revision(UUID projectId, Path root) throws Exception {
        Files.writeString(root.resolve("main.c"), "int main(){return 0;}");
        return new SourceRevisionView(
                UUID.randomUUID(), projectId, SourceRevisionType.ARCHIVE, "v1", "source.zip",
                null, null, null, null, root.toString(), null, true,
                UUID.randomUUID(), OffsetDateTime.now());
    }

    private EnvironmentView environment(UUID projectId, EnvironmentRole role, String workingDirectory) {
        return new EnvironmentView(
                UUID.randomUUID(), projectId, "env", role, role == EnvironmentRole.SOURCE_X86 ? "x86_64" : "riscv64",
                "127.0.0.1", 22, "root", UUID.randomUUID(), null, workingDirectory,
                EnvironmentStatus.AVAILABLE, true, null, null, UUID.randomUUID(), OffsetDateTime.now(), null);
    }

    private TaskResponse task(UUID projectId, UUID actorId, TaskCreateCommand command) {
        return new TaskResponse(UUID.randomUUID(), projectId, command.type(), TaskStatus.PENDING, 0,
                command.message(), OffsetDateTime.now(), null, null, null, null, null, Map.of());
    }

    private SourceDeployRunView run(UUID id, UUID projectId, UUID taskId, UUID revisionId, UUID environmentId, String remotePath, TaskStatus status) {
        return new SourceDeployRunView(id, projectId, taskId, revisionId, environmentId, remotePath,
                SourceDeployStrategy.TAR_OVER_SSH, false, status, null, null, null,
                JSONB.valueOf("{}"), null, null, OffsetDateTime.now());
    }
}
