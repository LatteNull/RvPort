package cn.rvport.backend.archive;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.artifact.StoredArtifactOwnerType;
import cn.rvport.backend.artifact.StoredArtifactResource;
import cn.rvport.backend.artifact.StoredArtifactService;
import cn.rvport.backend.artifact.StoredArtifactView;
import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.project.ProjectAccessService;
import cn.rvport.backend.source.SourceRepository;
import cn.rvport.backend.source.SourceRevisionType;
import cn.rvport.backend.source.SourceRevisionView;
import cn.rvport.backend.task.TaskCreateCommand;
import cn.rvport.backend.task.TaskRepository;
import cn.rvport.backend.task.TaskResponse;
import cn.rvport.backend.task.TaskService;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.workflow.ProjectContextService;
import cn.rvport.backend.workflow.ProjectContextSnapshot;
import cn.rvport.backend.workflow.StageReadinessService;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.ObjectWriter;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpStatus;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class ProjectArchiveServiceTests {

    @Mock private ProjectArchiveRepository archiveRepository;
    @Mock private ArchiveCandidateService candidateService;
    @Mock private SourceRepository sourceRepository;
    @Mock private ProjectAccessService projectAccessService;
    @Mock private TaskService taskService;
    @Mock private TaskRepository taskRepository;
    @Mock private ProjectContextService projectContextService;
    @Mock private StageReadinessService stageReadinessService;
    @Mock private StoredArtifactService storedArtifactService;

    private ProjectArchiveService service;

    @BeforeEach
    void setUp() {
        service = service(new ObjectMapper(), stageReadinessService);
    }

    @Test
    void createsArchiveForActiveRevisionAndUsesVersionLabel() {
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        SourceRevisionView revision = revision(projectId, "v2");
        TaskResponse task = task(projectId);
        ProjectArchiveView archive = archive(projectId, revision.id(), task.id(), null);
        when(sourceRepository.findActive(projectId)).thenReturn(Optional.of(revision));
        when(taskService.create(any())).thenReturn(task);
        when(archiveRepository.create(projectId, revision.id(), task.id(), "项目归档 - v2", actorId)).thenReturn(archive);

        ProjectArchiveCreateResponse response = service.createCurrent(projectId, actorId, false);

        assertThat(response.archiveId()).isEqualTo(archive.id());
        assertThat(response.sourceRevisionId()).isEqualTo(revision.id());
        ArgumentCaptor<TaskCreateCommand> command = ArgumentCaptor.forClass(TaskCreateCommand.class);
        verify(taskService).create(command.capture());
        assertThat(command.getValue().inputSnapshot().get("sourceRevisionId")).isEqualTo(revision.id().toString());
        verify(stageReadinessService).requireSatisfied(any(), any(), any(), any(), org.mockito.ArgumentMatchers.eq(false));
    }

    @Test
    void createsArchiveWithoutOptionalReadinessServiceAndFallsBackToRevisionId() {
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        SourceRevisionView revision = revision(projectId, " ");
        TaskResponse task = task(projectId);
        when(sourceRepository.findActive(projectId)).thenReturn(Optional.of(revision));
        when(taskService.create(any())).thenReturn(task);
        when(archiveRepository.create(projectId, revision.id(), task.id(), "项目归档 - " + revision.id(), actorId))
                .thenReturn(archive(projectId, revision.id(), task.id(), null));

        ProjectArchiveCreateResponse response = service(new ObjectMapper(), null).createCurrent(projectId, actorId, true);

        assertThat(response.task()).isEqualTo(task);
    }

    @Test
    void rejectsCreateWhenNoActiveRevisionExists() {
        UUID projectId = UUID.randomUUID();
        when(sourceRepository.findActive(projectId)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.createCurrent(projectId, UUID.randomUUID(), false))
                .isInstanceOfSatisfying(ApiException.class, ex -> {
                    assertThat(ex.status()).isEqualTo(HttpStatus.BAD_REQUEST);
                    assertThat(ex.code()).isEqualTo("ARCHIVE_SOURCE_REVISION_REQUIRED");
                });
    }

    @Test
    void returnsOverviewWithLatestArchiveOrNull() {
        UUID projectId = UUID.randomUUID();
        SourceRevisionView revision = revision(projectId, "v1");
        ProjectArchiveView archive = archive(projectId, revision.id(), UUID.randomUUID(), null);
        when(archiveRepository.latest(projectId)).thenReturn(Optional.of(archive), Optional.empty());
        when(archiveRepository.listItems(archive.id())).thenReturn(List.of());
        when(sourceRepository.findById(revision.id())).thenReturn(Optional.of(revision));

        assertThat(service.overview(projectId, UUID.randomUUID(), false).latestArchive()).isNotNull();
        assertThat(service.overview(projectId, UUID.randomUUID(), false).latestArchive()).isNull();
    }

    @Test
    void latestDistinguishesCurrentStaleAndEmpty() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        ProjectContextSnapshot context = new ProjectContextSnapshot(revisionId, 3L);
        ProjectArchiveView current = archive(projectId, revisionId, UUID.randomUUID(), null);
        when(projectContextService.snapshot(projectId)).thenReturn(context);
        when(archiveRepository.latest(projectId, revisionId)).thenReturn(Optional.of(current), Optional.empty(), Optional.empty());
        when(archiveRepository.latest(projectId)).thenReturn(Optional.of(current), Optional.empty());
        when(archiveRepository.listItems(current.id())).thenReturn(List.of());

        assertThat(service.latest(projectId, UUID.randomUUID(), false).freshness().name()).isEqualTo("CURRENT");
        assertThat(service.latest(projectId, UUID.randomUUID(), false).freshness().name()).isEqualTo("STALE");
        assertThat(service.latest(projectId, UUID.randomUUID(), false).freshness().name()).isEqualTo("EMPTY");
    }

    @Test
    void listsWithoutItemsAndMapsInvalidQuery() {
        UUID projectId = UUID.randomUUID();
        ProjectArchiveListRequest request = new ProjectArchiveListRequest(0, 1000, null, null, null, null, "createdAt", "desc");
        assertThat(new ProjectArchiveListRequest(1, 0, null, null, null, null, null, null)
                .normalizedPageSize()).isEqualTo(20);
        ProjectArchiveView archive = archive(projectId, null, UUID.randomUUID(), null);
        when(archiveRepository.count(projectId, request)).thenReturn(1L).thenThrow(new IllegalArgumentException("bad sort"));
        when(archiveRepository.list(projectId, request)).thenReturn(List.of(archive));

        var page = service.list(projectId, request, UUID.randomUUID(), false);
        assertThat(page.page()).isEqualTo(1);
        assertThat(page.pageSize()).isEqualTo(100);
        assertThat(page.items()).singleElement().satisfies(item -> assertThat(item.items()).isEmpty());

        assertThatThrownBy(() -> service.list(projectId, request, UUID.randomUUID(), false))
                .isInstanceOfSatisfying(ApiException.class, ex -> assertThat(ex.code()).isEqualTo("ARCHIVE_QUERY_INVALID"));
    }

    @Test
    void getsArchiveWithItemsAndRejectsUnknownArchive() {
        UUID projectId = UUID.randomUUID();
        ProjectArchiveView archive = archive(projectId, null, UUID.randomUUID(), null);
        ProjectArchiveItemView item = item(archive.id(), List.of(), Map.of("count", 1));
        when(archiveRepository.findById(archive.id())).thenReturn(Optional.of(archive));
        when(archiveRepository.listItems(archive.id())).thenReturn(List.of(item));

        assertThat(service.get(archive.id(), UUID.randomUUID(), false).items()).hasSize(1);
        assertThatThrownBy(() -> service.get(UUID.randomUUID(), UUID.randomUUID(), false))
                .isInstanceOfSatisfying(ApiException.class, ex -> assertThat(ex.code()).isEqualTo("ARCHIVE_NOT_FOUND"));
    }

    @Test
    void downloadsArchiveAndRejectsMissingArtifact() {
        UUID projectId = UUID.randomUUID();
        UUID artifactId = UUID.randomUUID();
        ProjectArchiveView archive = archive(projectId, null, UUID.randomUUID(), artifactId);
        StoredArtifactResource resource = resource(artifactId, "application/zip", "zip");
        when(archiveRepository.findById(archive.id())).thenReturn(Optional.of(archive));
        when(storedArtifactService.download(artifactId)).thenReturn(resource);

        ProjectArchiveDownload download = service.download(archive.id(), UUID.randomUUID(), false);
        assertThat(download.filename()).isEqualTo("rvport-archive-" + archive.id() + ".zip");
        assertThat(download.contentType()).isEqualTo("application/zip");

        ProjectArchiveView missing = archive(projectId, null, UUID.randomUUID(), null);
        when(archiveRepository.findById(missing.id())).thenReturn(Optional.of(missing));
        assertThatThrownBy(() -> service.download(missing.id(), UUID.randomUUID(), false))
                .isInstanceOfSatisfying(ApiException.class, ex -> assertThat(ex.code()).isEqualTo("ARCHIVE_ARTIFACT_NOT_FOUND"));
    }

    @Test
    void downloadsItemArtifactAndSanitizesUnsafeFilename() {
        UUID projectId = UUID.randomUUID();
        ProjectArchiveView archive = archive(projectId, null, UUID.randomUUID(), null);
        UUID artifactId = UUID.randomUUID();
        ArchiveArtifactRef ref = new ArchiveArtifactRef("HTML", artifactId, "REPORT", "text/html", "../report.html");
        ProjectArchiveItemView item = item(archive.id(), List.of(ref), Map.of());
        when(archiveRepository.findById(archive.id())).thenReturn(Optional.of(archive));
        when(archiveRepository.findItem(archive.id(), item.id())).thenReturn(Optional.of(item));
        when(storedArtifactService.download(artifactId)).thenReturn(resource(artifactId, "text/html", "html"));

        ProjectArchiveDownload download = service.downloadItem(archive.id(), item.id(), "html", UUID.randomUUID(), false);

        assertThat(download.filename()).isEqualTo("kb_scan-" + item.id() + ".html");
        assertThat(download.contentType()).isEqualTo("text/html");
    }

    @Test
    void fallsBackToMetadataJsonAndHandlesMissingFormats() {
        UUID projectId = UUID.randomUUID();
        ProjectArchiveView archive = archive(projectId, null, UUID.randomUUID(), null);
        ProjectArchiveItemView metadataItem = item(archive.id(), List.of(), Map.of("answer", 42));
        when(archiveRepository.findById(archive.id())).thenReturn(Optional.of(archive));
        when(archiveRepository.findItem(archive.id(), metadataItem.id())).thenReturn(Optional.of(metadataItem));

        ProjectArchiveDownload download = service.downloadItem(
                archive.id(), metadataItem.id(), "JSON", UUID.randomUUID(), false);
        assertThat(download.filename()).isEqualTo("kb_scan-" + metadataItem.id() + ".json");
        assertThat(download.resource()).isInstanceOf(ByteArrayResource.class);

        assertThatThrownBy(() -> service.downloadItem(
                archive.id(), metadataItem.id(), "HTML", UUID.randomUUID(), false))
                .isInstanceOfSatisfying(ApiException.class, ex -> assertThat(ex.code()).isEqualTo("ARCHIVE_ITEM_FORMAT_NOT_FOUND"));

        ArchiveArtifactRef nullArtifact = new ArchiveArtifactRef("HTML", null, "REPORT", "text/html", "report.html");
        ProjectArchiveItemView broken = item(archive.id(), List.of(nullArtifact), Map.of());
        when(archiveRepository.findItem(archive.id(), broken.id())).thenReturn(Optional.of(broken));
        assertThatThrownBy(() -> service.downloadItem(
                archive.id(), broken.id(), "HTML", UUID.randomUUID(), false))
                .isInstanceOfSatisfying(ApiException.class, ex -> assertThat(ex.code()).isEqualTo("ARCHIVE_ITEM_ARTIFACT_NOT_FOUND"));
    }

    @Test
    void mapsMetadataSerializationFailureAndMissingItem() throws Exception {
        ObjectMapper mapper = mock(ObjectMapper.class);
        ObjectWriter writer = mock(ObjectWriter.class);
        when(mapper.writerWithDefaultPrettyPrinter()).thenReturn(writer);
        when(writer.writeValueAsBytes(any())).thenThrow(new JsonProcessingException("broken") { });
        ProjectArchiveService failingService = service(mapper, stageReadinessService);
        UUID projectId = UUID.randomUUID();
        ProjectArchiveView archive = archive(projectId, null, UUID.randomUUID(), null);
        ProjectArchiveItemView item = item(archive.id(), List.of(), Map.of());
        when(archiveRepository.findById(archive.id())).thenReturn(Optional.of(archive));
        when(archiveRepository.findItem(archive.id(), item.id())).thenReturn(Optional.of(item));

        assertThatThrownBy(() -> failingService.downloadItem(
                archive.id(), item.id(), "JSON", UUID.randomUUID(), false))
                .isInstanceOfSatisfying(ApiException.class, ex -> assertThat(ex.code()).isEqualTo("ARCHIVE_ITEM_METADATA_INVALID"));

        assertThatThrownBy(() -> failingService.downloadItem(
                archive.id(), UUID.randomUUID(), "JSON", UUID.randomUUID(), false))
                .isInstanceOfSatisfying(ApiException.class, ex -> assertThat(ex.code()).isEqualTo("ARCHIVE_ITEM_NOT_FOUND"));
    }

    @Test
    void exposesInternalCandidatesAndStateTransitions() {
        UUID taskId = UUID.randomUUID();
        UUID archiveId = UUID.randomUUID();
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        ProjectArchiveView archive = archive(projectId, revisionId, taskId, null);
        ArchiveCandidateView candidate = new ArchiveCandidateView(
                UUID.randomUUID(), projectId, revisionId, ArchiveNodeType.KB_SCAN, ArchiveCandidateType.REPORT,
                "candidate", "report", UUID.randomUUID(), "Report", Map.of(), List.of(),
                ArchiveCandidateStatus.ACTIVE, OffsetDateTime.now(), OffsetDateTime.now());
        ProjectArchiveItemView createdItem = item(archiveId, List.of(), Map.of());
        when(archiveRepository.findByTaskId(taskId)).thenReturn(Optional.of(archive));
        when(candidateService.listActive(projectId, revisionId)).thenReturn(List.of(candidate));
        when(archiveRepository.markRunning(archiveId)).thenReturn(archive);
        when(archiveRepository.createItem(archiveId, candidate)).thenReturn(createdItem);
        when(archiveRepository.markSucceeded(any(), any(), org.mockito.ArgumentMatchers.anyLong(), any(), any())).thenReturn(archive);
        when(archiveRepository.markFailed(any(), any())).thenReturn(archive);

        assertThat(service.requireInternalByTaskId(taskId)).isEqualTo(archive);
        assertThat(service.activeCandidates(projectId, revisionId)).containsExactly(candidate);
        assertThat(service.markRunning(archiveId)).isEqualTo(archive);
        assertThat(service.createItem(archiveId, candidate)).isNotNull();
        assertThat(service.markSucceeded(archiveId, UUID.randomUUID(), 12, "sha", Map.of())).isEqualTo(archive);
        assertThat(service.markFailed(archiveId, Map.of())).isEqualTo(archive);

        assertThatThrownBy(() -> service.requireInternalByTaskId(UUID.randomUUID()))
                .isInstanceOfSatisfying(ApiException.class, ex -> assertThat(ex.code()).isEqualTo("ARCHIVE_NOT_FOUND"));
    }

    @Test
    void archiveItemFilenameAcceptsOnlySimpleNonBlankNames() {
        ProjectArchiveItemView item = item(UUID.randomUUID(), List.of(), Map.of());

        assertThat(safeFilename("report.html", item, "HTML")).isEqualTo("report.html");
        assertThat(safeFilename(null, item, "JSON")).endsWith(".json");
        assertThat(safeFilename(" ", item, "JSON")).endsWith(".json");
        assertThat(safeFilename("dir/report.html", item, "HTML")).endsWith(".html");
        assertThat(safeFilename("dir\\report.html", item, "HTML")).endsWith(".html");
        assertThat(safeFilename("report..html", item, "HTML")).endsWith(".html");
    }

    private String safeFilename(String filename, ProjectArchiveItemView item, String format) {
        return ReflectionTestUtils.invokeMethod(service, "safeFilename", filename, item, format);
    }

    private ProjectArchiveService service(ObjectMapper mapper, StageReadinessService readinessService) {
        return new ProjectArchiveService(
                archiveRepository, candidateService, sourceRepository, projectAccessService, taskService,
                taskRepository, projectContextService, readinessService, storedArtifactService, mapper);
    }

    private SourceRevisionView revision(UUID projectId, String label) {
        return new SourceRevisionView(
                UUID.randomUUID(), projectId, SourceRevisionType.GIT, label, null, "git", "main", "commit",
                null, "/work", null, true, UUID.randomUUID(), OffsetDateTime.now());
    }

    private TaskResponse task(UUID projectId) {
        return new TaskResponse(
                UUID.randomUUID(), projectId, "ARCHIVE_PROJECT", TaskStatus.PENDING, 0, "created",
                OffsetDateTime.now(), null, null, null, null, null, Map.of());
    }

    private ProjectArchiveView archive(UUID projectId, UUID revisionId, UUID taskId, UUID artifactId) {
        return new ProjectArchiveView(
                UUID.randomUUID(), projectId, revisionId, taskId, artifactId, "archive", TaskStatus.SUCCEEDED,
                Map.of(), artifactId == null ? null : 10L, artifactId == null ? null : "sha", UUID.randomUUID(),
                OffsetDateTime.now(), OffsetDateTime.now());
    }

    private ProjectArchiveItemView item(UUID archiveId, List<ArchiveArtifactRef> refs, Map<String, Object> metadata) {
        return new ProjectArchiveItemView(
                UUID.randomUUID(), archiveId, UUID.randomUUID(), ArchiveNodeType.KB_SCAN, ArchiveCandidateType.REPORT,
                "candidate", "report", UUID.randomUUID(), "Report", refs, metadata, OffsetDateTime.now());
    }

    private StoredArtifactResource resource(UUID artifactId, String contentType, String content) {
        StoredArtifactView artifact = new StoredArtifactView(
                artifactId, UUID.randomUUID(), UUID.randomUUID(), StoredArtifactOwnerType.ARCHIVE,
                UUID.randomUUID(), "ARCHIVE", "bucket", "key", contentType, content.length(), "sha", Map.of(),
                OffsetDateTime.now());
        return new StoredArtifactResource(artifact, new ByteArrayResource(content.getBytes()));
    }
}
