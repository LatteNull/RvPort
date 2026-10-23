package cn.rvport.backend.source.runtime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.config.RvPortProperties;
import cn.rvport.backend.credential.CredentialKind;
import cn.rvport.backend.credential.CredentialService;
import cn.rvport.backend.optimization.OptimizationCycleService;
import cn.rvport.backend.project.ProjectRepository;
import cn.rvport.backend.project.ProjectSourceInputType;
import cn.rvport.backend.project.ProjectStage;
import cn.rvport.backend.project.ProjectStatus;
import cn.rvport.backend.project.ProjectView;
import cn.rvport.backend.source.SourceRepository;
import cn.rvport.backend.source.SourceRevisionType;
import cn.rvport.backend.source.SourceRevisionView;
import cn.rvport.backend.task.TaskExecutionException;
import cn.rvport.backend.task.TaskEventService;
import cn.rvport.backend.task.TaskLogType;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.task.TaskView;
import cn.rvport.backend.task.ToolRunRepository;
import cn.rvport.backend.worker.TaskExecutionContext;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.time.OffsetDateTime;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.jupiter.api.io.TempDir;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class SourceFetchRuntimeServiceTests {

    @Mock
    private SourceRepository sourceRepository;

    @Mock
    private ProjectRepository projectRepository;

    @Mock
    private CredentialService credentialService;

    @Mock
    private ToolRunRepository toolRunRepository;

    @Mock
    private OptimizationCycleService optimizationCycleService;

    @Mock
    private TaskEventService taskEventService;

    @TempDir
    private Path tempDir;

    @Test
    void lostAttemptCannotActivateFetchedSourceOrOverwriteFailure() {
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        TaskExecutionContext execution = context(UUID.randomUUID(), projectId, actorId);
        when(projectRepository.findById(projectId)).thenReturn(java.util.Optional.of(project(projectId, actorId, null)));
        SourceFetchRuntimeService runtime = service(command -> {
            writeFile(command.worktreeDir(), "README.md", "fixture");
            org.mockito.Mockito.doThrow(new cn.rvport.backend.worker.TaskAttemptLostException()).when(execution).publish(any());
            return new GitSyncResult(0, "", "", "abc123", Duration.ofMillis(1));
        });
        assertThatThrownBy(() -> runtime.sync(input(projectId, UUID.randomUUID(), null, null, true), execution))
                .isInstanceOf(cn.rvport.backend.worker.TaskAttemptLostException.class);
        org.mockito.Mockito.verifyNoInteractions(sourceRepository, optimizationCycleService, taskEventService);
        verify(toolRunRepository, never()).finish(any(), any(), any(), any());
    }

    @Test
    void syncsGitSourceAndActivatesRevision() throws Exception {
        UUID projectId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        UUID importId = UUID.randomUUID();
        UUID toolRunId = UUID.randomUUID();
        TaskExecutionContext context = context(taskId, projectId, actorId);
        when(projectRepository.findById(projectId)).thenReturn(java.util.Optional.of(project(projectId, actorId, null)));
        when(toolRunRepository.create(eq(projectId), eq(taskId), eq("rvport-git-sync"), eq("1"), any(), eq(TaskStatus.RUNNING), any()))
                .thenReturn(toolRunId);
        when(sourceRepository.createGit(any(), eq(projectId), eq("v1"), eq("https://example.com/repo.git"), eq("main"), eq("abc123"),
                any(), eq("note"), eq(true), eq(actorId)))
                .thenAnswer(invocation -> revision(invocation.getArgument(0), projectId, invocation.getArgument(6), true, actorId));

        SourceFetchRuntimeService service = service(command -> {
            writeFile(command.worktreeDir(), "README.md", "demo");
            return new GitSyncResult(0, "clone ok", "", "abc123", Duration.ofMillis(25));
        });

        SourceRevisionView revision = service.sync(input(projectId, importId, "main", null, true), context);

        assertThat(revision.gitCommit()).isEqualTo("abc123");
        verify(sourceRepository).clearActive(projectId);
        verify(sourceRepository).completeImport(importId, revision.id());
        verify(projectRepository).lockSourceInputTypeIfEmpty(projectId, ProjectSourceInputType.GIT);
        verify(projectRepository).updateStage(projectId, ProjectStage.SOURCE_IMPORTED);
        verify(optimizationCycleService).createOrReuseActiveCycle(projectId, revision.id());
        verify(taskEventService).appendProjectContextChanged(
                eq(projectId),
                eq("context"),
                any(),
                eq(java.util.List.of("activeSourceRevision")),
                eq("项目源码版本已更新")
        );
        verify(toolRunRepository).finish(eq(toolRunId), eq(TaskStatus.SUCCEEDED), eq(0), any());
        verify(context).log(TaskLogType.STDOUT, "clone ok");
    }

    @Test
    void failsImportAndCleansTempWorktreeWhenGitFails() throws Exception {
        UUID projectId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        UUID importId = UUID.randomUUID();
        UUID toolRunId = UUID.randomUUID();
        TaskExecutionContext context = context(taskId, projectId, UUID.randomUUID());
        when(projectRepository.findById(projectId)).thenReturn(java.util.Optional.of(project(projectId, UUID.randomUUID(), null)));
        when(toolRunRepository.create(any(), any(), any(), any(), any(), any(), any())).thenReturn(toolRunId);
        SourceFetchRuntimeService service = service(command -> {
            writeFile(command.worktreeDir(), "partial.txt", "partial");
            return new GitSyncResult(1, "", "auth failed with ****", "", Duration.ofMillis(10));
        });

        assertThatThrownBy(() -> service.sync(input(projectId, importId, null, null, true), context))
                .isInstanceOf(TaskExecutionException.class)
                .hasMessage("Git 同步失败");

        assertThat(tempDir.resolve(projectId.toString()).resolve(".tmp-" + taskId)).doesNotExist();
        verify(sourceRepository).failImport(importId, "Git 同步失败");
        verify(sourceRepository, never()).createGit(any(), any(), any(), any(), any(), any(), any(), any(), anyBoolean(), any());
        verify(sourceRepository, never()).clearActive(projectId);
        verify(toolRunRepository).finish(eq(toolRunId), eq(TaskStatus.FAILED), eq(1), any());
    }

    @Test
    void decryptsGitCredentialOnlyWhenCredentialIdIsPresent() {
        UUID projectId = UUID.randomUUID();
        UUID credentialId = UUID.randomUUID();
        CredentialService.GitRuntimeCredential credential = new CredentialService.GitRuntimeCredential(
                credentialId,
                CredentialKind.GIT_TOKEN,
                "",
                "SecretToken"
        );
        when(toolRunRepository.create(any(), any(), any(), any(), any(), any(), any())).thenReturn(UUID.randomUUID());
        when(projectRepository.findById(projectId)).thenReturn(java.util.Optional.of(project(projectId, UUID.randomUUID(), null)));
        when(credentialService.gitRuntimeCredential(credentialId, projectId)).thenReturn(credential);
        when(sourceRepository.createGit(any(), eq(projectId), any(), any(), any(), eq("abc123"), any(), any(), eq(false), any()))
                .thenAnswer(invocation -> revision(invocation.getArgument(0), projectId, invocation.getArgument(6), false, invocation.getArgument(9)));
        SourceFetchRuntimeService service = service(command -> {
            assertThat(command.credential()).isSameAs(credential);
            try {
                Files.createDirectories(command.worktreeDir());
            } catch (Exception ex) {
                throw new RuntimeException(ex);
            }
            return new GitSyncResult(0, "", "", "abc123", Duration.ZERO);
        });

        service.sync(input(projectId, UUID.randomUUID(), null, credentialId, false), context(UUID.randomUUID(), projectId, UUID.randomUUID()));

        verify(credentialService).gitRuntimeCredential(credentialId, projectId);
    }

    @Test
    void rejectsGitSyncWhenProjectIsLockedToArchive() {
        UUID projectId = UUID.randomUUID();
        UUID importId = UUID.randomUUID();
        UUID toolRunId = UUID.randomUUID();
        when(toolRunRepository.create(any(), any(), any(), any(), any(), any(), any())).thenReturn(toolRunId);
        when(projectRepository.findById(projectId)).thenReturn(java.util.Optional.of(project(projectId, UUID.randomUUID(), ProjectSourceInputType.ARCHIVE)));
        SourceFetchRuntimeService service = service(command -> {
            throw new AssertionError("git client should not run");
        });

        assertThatThrownBy(() -> service.sync(input(projectId, importId, null, null, false), context(UUID.randomUUID(), projectId, UUID.randomUUID())))
                .isInstanceOf(TaskExecutionException.class)
                .hasMessage("项目源码来源已锁定为 ARCHIVE");

        verify(sourceRepository).failImport(importId, "项目源码来源已锁定为 ARCHIVE");
        verify(sourceRepository, never()).createGit(any(), any(), any(), any(), any(), any(), any(), any(), anyBoolean(), any());
    }

    @Test
    void rejectsNullIncompleteAndProjectMismatchedInputsBeforeCreatingToolRun() {
        SourceFetchRuntimeService service = service(command -> {
            throw new AssertionError("git client should not run");
        });
        UUID projectId = UUID.randomUUID();
        TaskExecutionContext context = context(UUID.randomUUID(), projectId, UUID.randomUUID());

        for (SourceGitSyncInput invalid : java.util.Arrays.asList(
                null,
                input(null, UUID.randomUUID(), null, null, false),
                input(projectId, null, null, null, false),
                new SourceGitSyncInput(projectId, UUID.randomUUID(), null, null, null, null, "v", null, false),
                new SourceGitSyncInput(projectId, UUID.randomUUID(), " ", null, null, null, "v", null, false))) {
            assertThatThrownBy(() -> service.sync(invalid, context))
                    .isInstanceOf(TaskExecutionException.class)
                    .hasMessage("Git 同步任务输入非法");
        }

        assertThatThrownBy(() -> service.sync(
                input(UUID.randomUUID(), UUID.randomUUID(), null, null, false), context))
                .isInstanceOf(TaskExecutionException.class)
                .hasMessage("Git 同步任务项目不匹配");
        verify(toolRunRepository, never()).create(any(), any(), any(), any(), any(), any(), any());
    }

    @Test
    void rejectsMissingProjectWithoutDeletingAnotherAttemptTemporaryDirectory() throws Exception {
        UUID projectId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        UUID importId = UUID.randomUUID();
        when(toolRunRepository.create(any(), any(), any(), any(), any(), any(), any())).thenReturn(UUID.randomUUID());
        when(projectRepository.findById(projectId)).thenReturn(java.util.Optional.empty());
        Path taskTemp = tempDir.resolve(projectId.toString()).resolve(".tmp-" + taskId);
        Files.createDirectories(taskTemp);
        Files.writeString(taskTemp.resolve("partial"), "data");

        assertThatThrownBy(() -> service(command -> {
            throw new AssertionError("git client should not run");
        }).sync(input(projectId, importId, null, null, false), context(taskId, projectId, UUID.randomUUID())))
                .isInstanceOf(TaskExecutionException.class)
                .hasMessage("项目不存在");

        assertThat(taskTemp.resolve("partial")).hasContent("data");
    }

    @Test
    void mapsUnexpectedAdapterFailureAndMarksImportFailed() {
        UUID projectId = UUID.randomUUID();
        UUID importId = UUID.randomUUID();
        UUID toolRunId = UUID.randomUUID();
        when(toolRunRepository.create(any(), any(), any(), any(), any(), any(), any())).thenReturn(toolRunId);
        when(projectRepository.findById(projectId))
                .thenReturn(java.util.Optional.of(project(projectId, UUID.randomUUID(), ProjectSourceInputType.GIT)));

        assertThatThrownBy(() -> service(command -> {
            throw new IllegalStateException("adapter broke");
        }).sync(input(projectId, importId, " ", null, false),
                context(UUID.randomUUID(), projectId, UUID.randomUUID())))
                .isInstanceOf(TaskExecutionException.class)
                .hasMessage("Git 同步失败")
                .hasCauseInstanceOf(IllegalStateException.class);

        verify(sourceRepository).failImport(importId, "Git 同步失败");
        verify(toolRunRepository).finish(eq(toolRunId), eq(TaskStatus.FAILED), eq(null), any());
    }

    @Test
    void utilityMethodsUseDefaultRootNormalizeTextAndHandleMissingCleanupPaths() {
        RvPortProperties defaults = new RvPortProperties(null, null, new RvPortProperties.Worker(false));
        SourceFetchRuntimeService defaultService = new SourceFetchRuntimeService(
                sourceRepository, projectRepository, credentialService, command -> null, toolRunRepository,
                defaults, optimizationCycleService, taskEventService);
        Path root = ReflectionTestUtils.invokeMethod(defaultService, "sourceRoot");
        assertThat(root).isAbsolute().isEqualTo(Path.of("runtime", "sources").toAbsolutePath().normalize());
        assertThat((String) ReflectionTestUtils.invokeMethod(defaultService, "blankToNull", (String) null)).isNull();
        assertThat((String) ReflectionTestUtils.invokeMethod(defaultService, "blankToNull", "  ")).isNull();
        assertThat((String) ReflectionTestUtils.invokeMethod(defaultService, "blankToNull", " value ")).isEqualTo("value");
        ReflectionTestUtils.invokeMethod(defaultService, "deleteRecursively", (Path) null);
        ReflectionTestUtils.invokeMethod(defaultService, "deleteRecursively", tempDir.resolve("missing"));

        RvPortProperties blankRuntime = new RvPortProperties(
                new RvPortProperties.Runtime("logs", "archives", "uploads", " "), null, new RvPortProperties.Worker(false));
        SourceFetchRuntimeService blankService = new SourceFetchRuntimeService(
                sourceRepository, projectRepository, credentialService, command -> null, toolRunRepository,
                blankRuntime, optimizationCycleService, taskEventService);
        assertThat((Path) ReflectionTestUtils.invokeMethod(blankService, "sourceRoot"))
                .isEqualTo(root);
    }

    @Test
    void failedCredentialedSyncRecordsCredentialPresenceAndIgnoresNullLogs() {
        UUID projectId = UUID.randomUUID();
        UUID importId = UUID.randomUUID();
        UUID credentialId = UUID.randomUUID();
        UUID toolRunId = UUID.randomUUID();
        CredentialService.GitRuntimeCredential credential = new CredentialService.GitRuntimeCredential(
                credentialId, CredentialKind.GIT_PASSWORD, "user", "secret");
        when(toolRunRepository.create(any(), any(), any(), any(), any(), any(), any())).thenReturn(toolRunId);
        when(projectRepository.findById(projectId))
                .thenReturn(java.util.Optional.of(project(projectId, UUID.randomUUID(), ProjectSourceInputType.GIT)));
        when(credentialService.gitRuntimeCredential(credentialId, projectId)).thenReturn(credential);

        assertThatThrownBy(() -> service(command -> new GitSyncResult(
                4, null, null, "", Duration.ofMillis(2)))
                .sync(input(projectId, importId, null, credentialId, false),
                        context(UUID.randomUUID(), projectId, UUID.randomUUID())))
                .isInstanceOf(TaskExecutionException.class);

        @SuppressWarnings("unchecked")
        ArgumentCaptor<java.util.Map<String, Object>> summary = ArgumentCaptor.forClass(java.util.Map.class);
        verify(toolRunRepository).finish(eq(toolRunId), eq(TaskStatus.FAILED), eq(4), summary.capture());
        assertThat(summary.getValue()).containsEntry("hasCredential", true);
    }

    private SourceFetchRuntimeService service(GitClientAdapter adapter) {
        return new SourceFetchRuntimeService(
                sourceRepository,
                projectRepository,
                credentialService,
                adapter,
                toolRunRepository,
                new RvPortProperties(new RvPortProperties.Runtime("logs", "archives", "uploads", tempDir.toString()), null, new RvPortProperties.Worker(false)),
                optimizationCycleService,
                taskEventService
        );
    }

    private SourceGitSyncInput input(UUID projectId, UUID sourceImportId, String branch, UUID credentialId, boolean activate) {
        return new SourceGitSyncInput(
                projectId,
                sourceImportId,
                "https://example.com/repo.git",
                branch,
                null,
                credentialId,
                "v1",
                "note",
                activate
        );
    }

    private TaskExecutionContext context(UUID taskId, UUID projectId, UUID actorId) {
        TaskExecutionContext context = org.mockito.Mockito.mock(TaskExecutionContext.class);
        org.mockito.Mockito.lenient().when(context.publish(any())).thenAnswer(call -> ((java.util.function.Supplier<?>) call.getArgument(0)).get());
        when(context.task()).thenReturn(new TaskView(
                taskId,
                projectId,
                "SOURCE_GIT_SYNC",
                TaskStatus.RUNNING,
                10,
                null,
                actorId,
                OffsetDateTime.now(),
                OffsetDateTime.now(),
                OffsetDateTime.now(),
                null,
                null,
                null,
                null,
                0
        ));
        return context;
    }

    private SourceRevisionView revision(UUID id, UUID projectId, String workingCopyPath, boolean active, UUID actorId) {
        return new SourceRevisionView(
                id,
                projectId,
                SourceRevisionType.GIT,
                "v1",
                "https://example.com/repo.git",
                "https://example.com/repo.git",
                "main",
                "abc123",
                null,
                workingCopyPath,
                "note",
                active,
                actorId,
                OffsetDateTime.now()
        );
    }

    private ProjectView project(UUID projectId, UUID actorId, ProjectSourceInputType sourceInputType) {
        return new ProjectView(
                projectId,
                "demo",
                null,
                "x86_64",
                "riscv64",
                ProjectStage.PROJECT_CREATED,
                ProjectStatus.ACTIVE,
                sourceInputType,
                actorId,
                OffsetDateTime.now(),
                null
        );
    }

    private void writeFile(Path directory, String filename, String content) {
        try {
            Files.createDirectories(directory);
            Files.writeString(directory.resolve(filename), content);
        } catch (Exception ex) {
            throw new IllegalStateException(ex);
        }
    }
}
