package cn.rvport.backend.source;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.when;

import cn.rvport.backend.audit.AuditLogService;
import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.config.RvPortProperties;
import cn.rvport.backend.credential.CredentialKind;
import cn.rvport.backend.credential.CredentialService;
import cn.rvport.backend.credential.CredentialStatus;
import cn.rvport.backend.credential.CredentialView;
import cn.rvport.backend.optimization.OptimizationCycleService;
import cn.rvport.backend.project.ProjectRepository;
import cn.rvport.backend.project.ProjectSourceInputType;
import cn.rvport.backend.project.ProjectStage;
import cn.rvport.backend.project.ProjectStatus;
import cn.rvport.backend.project.ProjectView;
import cn.rvport.backend.project.ProjectAccessService;
import cn.rvport.backend.source.archive.SourceArchiveExtraction;
import cn.rvport.backend.source.archive.SourceArchiveExtractor;
import cn.rvport.backend.source.archive.SourceArchiveException;
import cn.rvport.backend.source.archive.SourceArchiveErrorCode;
import cn.rvport.backend.task.RvPortTaskTypes;
import cn.rvport.backend.task.TaskCreateCommand;
import cn.rvport.backend.task.TaskEventService;
import cn.rvport.backend.task.TaskResponse;
import cn.rvport.backend.task.TaskService;
import cn.rvport.backend.task.TaskStatus;
import java.nio.file.Path;
import java.nio.file.Files;
import java.time.OffsetDateTime;
import java.util.Optional;
import java.util.UUID;
import java.io.IOException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.jupiter.api.io.TempDir;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class SourceServiceTests {

    @Mock
    private SourceRepository sourceRepository;

    @Mock
    private ProjectRepository projectRepository;

    @Mock
    private CredentialService credentialService;

    @Mock
    private TaskService taskService;

    @Mock
    private AuditLogService auditLogService;

    @Mock
    private ProjectAccessService projectAccessService;

    @Mock
    private SourceArchiveExtractor archiveExtractor;

    @Mock
    private OptimizationCycleService optimizationCycleService;

    @Mock
    private TaskEventService taskEventService;

    @TempDir
    private Path tempDir;

    @Test
    void createsGitSyncTaskWithSafeInputSnapshot() {
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        UUID credentialId = UUID.randomUUID();
        UUID importId = UUID.randomUUID();
        SourceService service = service();
        when(projectAccessService.requireProjectAccess(projectId, actorId, false)).thenReturn(project(projectId, actorId));
        when(credentialService.requireActive(credentialId, projectId)).thenReturn(credential(projectId, credentialId, actorId));
        when(sourceRepository.createImport(projectId, null, SourceRevisionType.GIT, TaskStatus.PENDING))
                .thenReturn(sourceImport(importId, projectId, null, null, TaskStatus.PENDING));
        TaskResponse task = task(projectId);
        when(taskService.create(any())).thenReturn(task);
        when(sourceRepository.attachTask(importId, task.id(), task.status()))
                .thenReturn(sourceImport(importId, projectId, null, task.id(), task.status()));

        service.gitSync(projectId, new GitSyncRequest(
                "https://example.com/repo.git",
                "main",
                null,
                credentialId,
                null,
                null,
                null,
                null,
                null,
                "v1",
                null,
                true
        ), actorId, false, new MockHttpServletRequest());

        ArgumentCaptor<TaskCreateCommand> commandCaptor = ArgumentCaptor.forClass(TaskCreateCommand.class);
        verify(taskService).create(commandCaptor.capture());
        assertThat(commandCaptor.getValue().type()).isEqualTo(RvPortTaskTypes.SOURCE_GIT_SYNC);
        assertThat(commandCaptor.getValue().inputSnapshot().get("credentialId")).isEqualTo(credentialId);
        assertThat(commandCaptor.getValue().inputSnapshot().get("gitUrl")).isEqualTo("https://example.com/repo.git");
        assertThat(commandCaptor.getValue().inputSnapshot()).doesNotContainKey("password");
    }

    @Test
    void createsGitSyncTaskWithNormalizedGitUrl() {
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        UUID importId = UUID.randomUUID();
        SourceService service = service();
        when(projectAccessService.requireProjectAccess(projectId, actorId, false)).thenReturn(project(projectId, actorId));
        when(sourceRepository.createImport(projectId, null, SourceRevisionType.GIT, TaskStatus.PENDING))
                .thenReturn(sourceImport(importId, projectId, null, null, TaskStatus.PENDING));
        TaskResponse task = task(projectId);
        when(taskService.create(any())).thenReturn(task);
        when(sourceRepository.attachTask(importId, task.id(), task.status()))
                .thenReturn(sourceImport(importId, projectId, null, task.id(), task.status()));

        service.gitSync(projectId, new GitSyncRequest(
                "https://example.com/org/repo/",
                "main",
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                "v1",
                null,
                true
        ), actorId, false, new MockHttpServletRequest());

        ArgumentCaptor<TaskCreateCommand> commandCaptor = ArgumentCaptor.forClass(TaskCreateCommand.class);
        verify(taskService).create(commandCaptor.capture());
        assertThat(commandCaptor.getValue().inputSnapshot().get("gitUrl")).isEqualTo("https://example.com/org/repo.git");
    }

    @Test
    void rejectsGitUrlWithEmbeddedCredential() {
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        SourceService service = service();
        when(projectAccessService.requireProjectAccess(projectId, actorId, false)).thenReturn(project(projectId, actorId));

        assertThatThrownBy(() -> service.gitSync(projectId, new GitSyncRequest(
                "https://user:secret@example.com/repo.git",
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null
        ), actorId, false, new MockHttpServletRequest()))
                .isInstanceOf(ApiException.class)
                .hasMessage("Git URL 不能包含用户名、密码或 token");
    }

    @Test
    void uploadsArchiveAndDoesNotExposeLocalPath() {
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        SourceService service = service();
        when(projectAccessService.requireProjectAccess(projectId, actorId, false)).thenReturn(project(projectId, actorId));
        when(archiveExtractor.extract(any(), eq("source.zip"), any()))
                .thenAnswer(invocation -> new SourceArchiveExtraction(invocation.getArgument(2), 1));
        when(sourceRepository.createArchive(any(), eq(projectId), eq("v1"), eq("source.zip"), any(), any(), eq("note"), eq(true), eq(actorId)))
                .thenAnswer(invocation -> sourceRevision(invocation.getArgument(0), projectId, "source.zip", true, actorId));
        when(sourceRepository.createImport(eq(projectId), any(), eq(SourceRevisionType.ARCHIVE), eq(TaskStatus.SUCCEEDED)))
                .thenAnswer(invocation -> sourceImport(UUID.randomUUID(), projectId, invocation.getArgument(1), null, TaskStatus.SUCCEEDED));

        SourceArchiveResponse response = service.uploadArchive(
                projectId,
                new MockMultipartFile("file", "../source.zip", "application/zip", "demo".getBytes()),
                "v1",
                "note",
                true,
                actorId,
                false,
                new MockHttpServletRequest()
        );

        assertThat(response.sourceRevision().sourceUri()).isEqualTo("source.zip");
        assertThat(response.sourceRevision().toString()).doesNotContain(tempDir.toString());
        verify(sourceRepository).clearActive(projectId);
        verify(taskEventService).appendProjectContextChanged(
                eq(projectId),
                eq("context"),
                any(),
                eq(java.util.List.of("activeSourceRevision")),
                eq("项目源码版本已更新")
        );
    }

    @Test
    void listRejectsMissingProjectAndUploadRejectsEmptyArchive() {
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        SourceService service = service();
        when(projectAccessService.requireProjectAccess(projectId, actorId, false))
                .thenThrow(new ApiException(org.springframework.http.HttpStatus.NOT_FOUND, "PROJECT_NOT_FOUND", "项目不存在"));

        assertThatThrownBy(() -> service.list(projectId, new SourceListRequest(null, null, 1, 20), actorId, false))
                .isInstanceOf(ApiException.class)
                .hasMessage("项目不存在");

        UUID uploadActorId = UUID.randomUUID();
        when(projectAccessService.requireProjectAccess(projectId, uploadActorId, false)).thenReturn(project(projectId, uploadActorId));
        assertThatThrownBy(() -> service.uploadArchive(
                projectId, null, "v1", null, true, uploadActorId, false, new MockHttpServletRequest()))
                .isInstanceOf(ApiException.class)
                .hasMessage("源码包不能为空");
        assertThatThrownBy(() -> service.uploadArchive(
                projectId,
                new MockMultipartFile("file", "empty.zip", "application/zip", new byte[0]),
                "v1",
                null,
                true,
                uploadActorId,
                false,
                new MockHttpServletRequest()
        )).isInstanceOf(ApiException.class)
                .hasMessage("源码包不能为空");
    }

    @Test
    void activateRejectsMissingOrCrossProjectRevision() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        SourceService service = service();
        UUID actorId = UUID.randomUUID();
        when(projectAccessService.requireSourceRevisionAccess(projectId, revisionId, actorId, false))
                .thenThrow(new ApiException(org.springframework.http.HttpStatus.NOT_FOUND, "SOURCE_REVISION_NOT_FOUND", "源码版本不存在"));

        assertThatThrownBy(() -> service.activate(projectId, revisionId, actorId, false, new MockHttpServletRequest()))
                .isInstanceOf(ApiException.class)
                .hasMessage("源码版本不存在");

        UUID otherRevisionId = UUID.randomUUID();
        when(projectAccessService.requireSourceRevisionAccess(projectId, otherRevisionId, actorId, false))
                .thenThrow(new ApiException(org.springframework.http.HttpStatus.NOT_FOUND, "SOURCE_REVISION_NOT_FOUND", "源码版本不存在"));

        assertThatThrownBy(() -> service.activate(projectId, otherRevisionId, actorId, false, new MockHttpServletRequest()))
                .isInstanceOf(ApiException.class)
                .hasMessage("源码版本不存在");
    }

    @Test
    void uploadArchiveDoesNotClearActiveWhenActivateIsFalse() {
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        SourceService service = service();
        when(projectAccessService.requireProjectAccess(projectId, actorId, false)).thenReturn(project(projectId, actorId));
        when(archiveExtractor.extract(any(), eq("source.zip"), any()))
                .thenAnswer(invocation -> new SourceArchiveExtraction(invocation.getArgument(2), 1));
        when(sourceRepository.createArchive(any(), eq(projectId), eq("v1"), eq("source.zip"), any(), any(), eq(null), eq(false), eq(actorId)))
                .thenAnswer(invocation -> sourceRevision(invocation.getArgument(0), projectId, "source.zip", false, actorId));
        when(sourceRepository.createImport(eq(projectId), any(), eq(SourceRevisionType.ARCHIVE), eq(TaskStatus.SUCCEEDED)))
                .thenAnswer(invocation -> sourceImport(UUID.randomUUID(), projectId, invocation.getArgument(1), null, TaskStatus.SUCCEEDED));

        SourceArchiveResponse response = service.uploadArchive(
                projectId,
                new MockMultipartFile("file", "source.zip", "application/zip", "demo".getBytes()),
                "v1",
                null,
                false,
                actorId,
                false,
                new MockHttpServletRequest()
        );

        assertThat(response.sourceRevision().active()).isFalse();
        verify(sourceRepository, never()).clearActive(projectId);
    }

    @Test
    void gitSyncCreatesTokenCredentialWithoutLeakingSecret() {
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        UUID importId = UUID.randomUUID();
        UUID credentialId = UUID.randomUUID();
        SourceService service = service();
        when(projectAccessService.requireProjectAccess(projectId, actorId, false)).thenReturn(project(projectId, actorId));
        when(credentialService.create(any())).thenReturn(credential(projectId, credentialId, actorId));
        when(sourceRepository.createImport(projectId, null, SourceRevisionType.GIT, TaskStatus.PENDING))
                .thenReturn(sourceImport(importId, projectId, null, null, TaskStatus.PENDING));
        TaskResponse task = task(projectId);
        when(taskService.create(any())).thenReturn(task);
        when(sourceRepository.attachTask(importId, task.id(), task.status()))
                .thenReturn(sourceImport(importId, projectId, null, task.id(), task.status()));

        service.gitSync(projectId, new GitSyncRequest(
                "https://example.com/repo.git",
                null,
                null,
                null,
                CredentialKind.GIT_TOKEN,
                "git",
                null,
                "SecretToken123",
                null,
                null,
                null,
                true
        ), actorId, false, new MockHttpServletRequest());

        ArgumentCaptor<TaskCreateCommand> commandCaptor = ArgumentCaptor.forClass(TaskCreateCommand.class);
        verify(taskService).create(commandCaptor.capture());
        assertThat(commandCaptor.getValue().inputSnapshot().get("credentialId")).isEqualTo(credentialId);
        assertThat(commandCaptor.getValue().inputSnapshot().toString()).doesNotContain("SecretToken123");
    }

    @Test
    void gitSyncAllowsProjectAlreadyLockedToGit() {
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        UUID importId = UUID.randomUUID();
        SourceService service = service();
        when(projectAccessService.requireProjectAccess(projectId, actorId, false))
                .thenReturn(project(projectId, actorId, ProjectSourceInputType.GIT));
        when(sourceRepository.createImport(projectId, null, SourceRevisionType.GIT, TaskStatus.PENDING))
                .thenReturn(sourceImport(importId, projectId, null, null, TaskStatus.PENDING));
        TaskResponse task = task(projectId);
        when(taskService.create(any())).thenReturn(task);
        when(sourceRepository.attachTask(importId, task.id(), task.status()))
                .thenReturn(sourceImport(importId, projectId, null, task.id(), task.status()));

        TaskResponse response = service.gitSync(projectId, new GitSyncRequest(
                "https://example.com/repo.git",
                "main",
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                "v2",
                null,
                true
        ), actorId, false, new MockHttpServletRequest());

        assertThat(response.id()).isEqualTo(task.id());
        verify(taskService).create(any());
    }

    @Test
    void gitSyncCreatesDefaultPasswordCredential() {
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        UUID importId = UUID.randomUUID();
        UUID credentialId = UUID.randomUUID();
        SourceService service = service();
        when(projectAccessService.requireProjectAccess(projectId, actorId, false)).thenReturn(project(projectId, actorId));
        when(credentialService.create(any())).thenReturn(credential(projectId, credentialId, actorId));
        when(sourceRepository.createImport(projectId, null, SourceRevisionType.GIT, TaskStatus.PENDING))
                .thenReturn(sourceImport(importId, projectId, null, null, TaskStatus.PENDING));
        TaskResponse task = task(projectId);
        when(taskService.create(any())).thenReturn(task);
        when(sourceRepository.attachTask(importId, task.id(), task.status()))
                .thenReturn(sourceImport(importId, projectId, null, task.id(), task.status()));

        service.gitSync(projectId, new GitSyncRequest("https://example.com/repo.git", null, null, null,
                null, "git password", "builder", " password ", null, null, null, true),
                actorId, false, new MockHttpServletRequest());

        ArgumentCaptor<TaskCreateCommand> taskCommand = ArgumentCaptor.forClass(TaskCreateCommand.class);
        verify(taskService).create(taskCommand.capture());
        assertThat(taskCommand.getValue().inputSnapshot().get("credentialId")).isEqualTo(credentialId);
        assertThat(taskCommand.getValue().inputSnapshot().toString()).doesNotContain("password");
    }

    @Test
    void runtimePathsUseDefaultsWhenRuntimeOrConfiguredDirectoriesAreMissing() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        SourceService noRuntime = service(new RvPortProperties(null, null, new RvPortProperties.Worker(false)));
        SourceService blankDirectories = service(new RvPortProperties(
                new RvPortProperties.Runtime(null, null, " ", " "), null, new RvPortProperties.Worker(false)));

        Path defaultArchive = ReflectionTestUtils.invokeMethod(noRuntime, "archiveTarget", projectId, revisionId, "source.zip");
        Path blankArchive = ReflectionTestUtils.invokeMethod(blankDirectories, "archiveTarget", projectId, revisionId, "source.zip");
        Path defaultSource = ReflectionTestUtils.invokeMethod(noRuntime, "sourceTarget", projectId, revisionId);
        Path blankSource = ReflectionTestUtils.invokeMethod(blankDirectories, "sourceTarget", projectId, revisionId);

        assertThat(defaultArchive.toString()).endsWith(Path.of(projectId.toString(), revisionId.toString(), "source.zip").toString());
        assertThat(blankArchive).isEqualTo(defaultArchive);
        assertThat(defaultSource.toString()).endsWith(Path.of(projectId.toString(), revisionId.toString()).toString());
        assertThat(blankSource).isEqualTo(defaultSource);
        assertThat((String) ReflectionTestUtils.invokeMethod(noRuntime, "blankToNull", "  ")).isNull();
    }

    @Test
    void recursiveCleanupAcceptsNullAndMissingPathsAndDeletesExistingTree() throws Exception {
        SourceService service = service();
        ReflectionTestUtils.invokeMethod(service, "deleteRecursively", (Path) null);
        ReflectionTestUtils.invokeMethod(service, "deleteRecursively", tempDir.resolve("missing"));
        Path root = Files.createDirectories(tempDir.resolve("cleanup/child"));
        Files.writeString(root.resolve("file.txt"), "content");

        ReflectionTestUtils.invokeMethod(service, "deleteRecursively", tempDir.resolve("cleanup"));

        assertThat(tempDir.resolve("cleanup")).doesNotExist();
    }

    @Test
    void uploadArchiveSaveFailureMapsToApiError() {
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        SourceService service = service();
        when(projectAccessService.requireProjectAccess(projectId, actorId, false)).thenReturn(project(projectId, actorId));

        assertThatThrownBy(() -> service.uploadArchive(
                projectId,
                failingMultipartFile(),
                "v1",
                null,
                true,
                actorId,
                false,
                new MockHttpServletRequest()
        )).isInstanceOf(ApiException.class)
                .hasMessage("源码包保存失败");
    }

    @Test
    void archiveUploadRejectsLockedGitProjectBeforeSaving() {
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        SourceService service = service();
        when(projectAccessService.requireProjectAccess(projectId, actorId, false))
                .thenReturn(project(projectId, actorId, ProjectSourceInputType.GIT));

        assertThatThrownBy(() -> service.uploadArchive(
                projectId,
                new MockMultipartFile("file", "source.zip", "application/zip", "demo".getBytes()),
                "v1",
                null,
                true,
                actorId,
                false,
                new MockHttpServletRequest()
        )).isInstanceOf(ApiException.class)
                .hasMessage("项目源码来源已锁定为 GIT");

        verify(archiveExtractor, never()).extract(any(), any(), any());
        verify(sourceRepository, never()).createArchive(any(), any(), any(), any(), any(), any(), any(), anyBoolean(), any());
    }

    @Test
    void archiveExtractionFailureDoesNotCreateRevisionOrLockProject() {
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        SourceService service = service();
        when(projectAccessService.requireProjectAccess(projectId, actorId, false)).thenReturn(project(projectId, actorId));
        when(archiveExtractor.extract(any(), eq("source.zip"), any()))
                .thenThrow(new SourceArchiveException(SourceArchiveErrorCode.SOURCE_ARCHIVE_UNSUPPORTED_STRUCTURE, "源码包结构无效"));

        assertThatThrownBy(() -> service.uploadArchive(
                projectId,
                new MockMultipartFile("file", "source.zip", "application/zip", "demo".getBytes()),
                "v1",
                null,
                true,
                actorId,
                false,
                new MockHttpServletRequest()
        )).isInstanceOf(ApiException.class)
                .hasMessage("源码包结构无效");

        verify(sourceRepository, never()).createArchive(any(), any(), any(), any(), any(), any(), any(), anyBoolean(), any());
        verify(projectRepository, never()).lockSourceInputTypeIfEmpty(any(), any());
    }

    @Test
    void gitSyncRejectsLockedArchiveProjectBeforeCreatingImport() {
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        SourceService service = service();
        when(projectAccessService.requireProjectAccess(projectId, actorId, false))
                .thenReturn(project(projectId, actorId, ProjectSourceInputType.ARCHIVE));

        assertThatThrownBy(() -> service.gitSync(projectId, new GitSyncRequest(
                "https://example.com/repo.git",
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null
        ), actorId, false, new MockHttpServletRequest()))
                .isInstanceOf(ApiException.class)
                .hasMessage("项目源码来源已锁定为 ARCHIVE");

        verify(sourceRepository, never()).createImport(any(), any(), any(), any());
        verify(taskService, never()).create(any());
    }

    private SourceService service() {
        return service(new RvPortProperties(new RvPortProperties.Runtime(null, null, tempDir.toString(), tempDir.resolve("sources").toString()), null, new RvPortProperties.Worker(false)));
    }

    private SourceService service(RvPortProperties properties) {
        return new SourceService(
                sourceRepository,
                projectRepository,
                credentialService,
                taskService,
                new GitUrlValidator(),
                properties,
                auditLogService,
                projectAccessService,
                archiveExtractor,
                optimizationCycleService,
                taskEventService
        );
    }

    @Test
    void activatesSourceRevisionAndPublishesContextChangedEvent() {
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        SourceService service = service();
        SourceRevisionView revision = sourceRevision(revisionId, projectId, "source.zip", true, actorId);
        when(sourceRepository.activate(projectId, revisionId)).thenReturn(revision);

        SourceRevisionResponse response = service.activate(projectId, revisionId, actorId, false, new MockHttpServletRequest());

        assertThat(response.id()).isEqualTo(revisionId);
        assertThat(response.active()).isTrue();
        verify(projectAccessService).requireSourceRevisionAccess(projectId, revisionId, actorId, false);
        verify(sourceRepository).clearActive(projectId);
        verify(projectRepository).updateStage(projectId, ProjectStage.SOURCE_IMPORTED);
        verify(optimizationCycleService).createOrReuseActiveCycle(projectId, revisionId);
        verify(taskEventService).appendProjectContextChanged(
                eq(projectId),
                eq("context"),
                any(),
                eq(java.util.List.of("activeSourceRevision")),
                eq("项目源码版本已激活")
        );
    }

    private ProjectView project(UUID projectId, UUID createdBy) {
        return project(projectId, createdBy, null);
    }

    private ProjectView project(UUID projectId, UUID createdBy, ProjectSourceInputType sourceInputType) {
        return new ProjectView(
                projectId,
                "demo",
                null,
                "x86_64",
                "riscv64",
                ProjectStage.PROJECT_CREATED,
                ProjectStatus.ACTIVE,
                sourceInputType,
                createdBy,
                OffsetDateTime.now(),
                null
        );
    }

    private CredentialView credential(UUID projectId, UUID credentialId, UUID ownerId) {
        return new CredentialView(
                credentialId,
                projectId,
                ownerId,
                CredentialKind.GIT_TOKEN,
                "git",
                "****1234",
                "local-v1",
                CredentialStatus.ACTIVE,
                OffsetDateTime.now(),
                null
        );
    }

    private SourceRevisionView sourceRevision(UUID id, UUID projectId, String sourceUri, boolean active, UUID createdBy) {
        return new SourceRevisionView(
                id,
                projectId,
                SourceRevisionType.ARCHIVE,
                "v1",
                sourceUri,
                null,
                null,
                null,
                null,
                null,
                "note",
                active,
                createdBy,
                OffsetDateTime.now()
        );
    }

    private SourceImportView sourceImport(UUID id, UUID projectId, UUID revisionId, UUID taskId, TaskStatus status) {
        return new SourceImportView(id, projectId, revisionId, taskId, SourceRevisionType.ARCHIVE, status, null, OffsetDateTime.now());
    }

    private TaskResponse task(UUID projectId) {
        return new TaskResponse(
                UUID.randomUUID(),
                projectId,
                RvPortTaskTypes.SOURCE_GIT_SYNC,
                TaskStatus.PENDING,
                0,
                "Git 同步任务已创建",
                OffsetDateTime.now(),
                null,
                null,
                null,
                null,
                null,
                java.util.Map.of()
        );
    }

    private MultipartFile failingMultipartFile() {
        return new MockMultipartFile("file", "source.zip", "application/zip", "demo".getBytes()) {
            @Override
            public void transferTo(java.io.File dest) throws IOException, IllegalStateException {
                throw new IOException("disk full");
            }

            @Override
            public void transferTo(Path dest) throws IOException, IllegalStateException {
                throw new IOException("disk full");
            }
        };
    }
}
