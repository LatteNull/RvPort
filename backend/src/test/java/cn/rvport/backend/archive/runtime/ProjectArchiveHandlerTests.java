package cn.rvport.backend.archive.runtime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.archive.ArchiveArtifactRef;
import cn.rvport.backend.archive.ArchiveCandidateStatus;
import cn.rvport.backend.archive.ArchiveCandidateType;
import cn.rvport.backend.archive.ArchiveCandidateView;
import cn.rvport.backend.archive.ArchiveNodeType;
import cn.rvport.backend.archive.ProjectArchiveInput;
import cn.rvport.backend.archive.ProjectArchiveItemView;
import cn.rvport.backend.archive.ProjectArchiveService;
import cn.rvport.backend.archive.ProjectArchiveView;
import cn.rvport.backend.artifact.StoredArtifactCreateCommand;
import cn.rvport.backend.artifact.StoredArtifactOwnerType;
import cn.rvport.backend.artifact.StoredArtifactResource;
import cn.rvport.backend.artifact.StoredArtifactService;
import cn.rvport.backend.artifact.StoredArtifactView;
import cn.rvport.backend.task.RvPortTaskTypes;
import cn.rvport.backend.task.TaskErrorCode;
import cn.rvport.backend.task.TaskExecutionException;
import cn.rvport.backend.task.TaskLogType;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.task.TaskView;
import cn.rvport.backend.worker.TaskExecutionContext;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.core.io.Resource;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class ProjectArchiveHandlerTests {

    private static final UUID ARCHIVE_ID = UUID.randomUUID();
    private static final UUID PROJECT_ID = UUID.randomUUID();
    private static final UUID REVISION_ID = UUID.randomUUID();
    private static final UUID TASK_ID = UUID.randomUUID();
    private static final UUID ARTIFACT_ID = UUID.randomUUID();
    private static final OffsetDateTime NOW = OffsetDateTime.parse("2026-01-01T00:00:00Z");

    @Mock
    private ProjectArchiveService archiveService;
    @Mock
    private StoredArtifactService storedArtifactService;
    @Mock
    private TaskExecutionContext context;

    private ProjectArchiveHandler handler;

    @BeforeEach
    void setUp() {
        lenient().when(context.publish(any())).thenAnswer(call -> ((java.util.function.Supplier<?>) call.getArgument(0)).get());
        handler = new ProjectArchiveHandler(archiveService, storedArtifactService, new ObjectMapper());
        lenient().when(context.task()).thenReturn(task());
    }

    @Test
    void lostAttemptCannotFailOrPublishArchive() {
        when(archiveService.requireInternalByTaskId(TASK_ID)).thenReturn(archive());
        when(context.input(ProjectArchiveInput.class)).thenReturn(new ProjectArchiveInput(PROJECT_ID, REVISION_ID));
        org.mockito.Mockito.doThrow(new cn.rvport.backend.worker.TaskAttemptLostException()).when(context).publish(any());
        assertThatThrownBy(() -> handler.handle(context))
                .isInstanceOf(cn.rvport.backend.worker.TaskAttemptLostException.class);
        verify(archiveService, never()).markRunning(any());
        verify(archiveService, never()).markFailed(any(), any());
        verify(archiveService, never()).markSucceeded(any(), any(), org.mockito.ArgumentMatchers.anyLong(), any(), any());
        org.mockito.Mockito.verifyNoInteractions(storedArtifactService);
    }

    @Test
    void createsArchiveZipAndUsesSafeEntryNames() throws Exception {
        ProjectArchiveView archive = archive();
        UUID sourceArtifactId = UUID.randomUUID();
        ArchiveCandidateView candidate = candidate();
        ProjectArchiveItemView item = item(candidate, List.of(
                new ArchiveArtifactRef("HTML", sourceArtifactId, "REPORT", "text/html", "../unsafe.html"),
                new ArchiveArtifactRef("JSON", null, "RAW_RESULT", "application/json", "result.json")));
        when(archiveService.requireInternalByTaskId(TASK_ID)).thenReturn(archive);
        when(context.input(ProjectArchiveInput.class)).thenReturn(new ProjectArchiveInput(PROJECT_ID, REVISION_ID));
        when(archiveService.activeCandidates(PROJECT_ID, REVISION_ID)).thenReturn(List.of(candidate));
        when(archiveService.createItem(ARCHIVE_ID, candidate)).thenReturn(item);
        when(storedArtifactService.download(sourceArtifactId)).thenReturn(resource(sourceArtifactId, "payload"));
        when(storedArtifactService.store(any(), eq(context))).thenReturn(storedArtifact());

        assertThat(handler.taskType()).isEqualTo(RvPortTaskTypes.ARCHIVE_PROJECT);
        assertThat(handler.handle(context).message()).isEqualTo("项目归档完成");

        ArgumentCaptor<StoredArtifactCreateCommand> command = ArgumentCaptor.forClass(StoredArtifactCreateCommand.class);
        verify(storedArtifactService).store(command.capture(), eq(context));
        assertThat(command.getValue().ownerType()).isEqualTo(StoredArtifactOwnerType.ARCHIVE);
        assertThat(command.getValue().artifactType()).isEqualTo("PROJECT_ARCHIVE_ZIP");
        assertThat(zipEntries(command.getValue().content())).containsExactly(
                "manifest.json",
                "summary.json",
                "items/kb_scan/report/summary-" + item.id() + ".json",
                "items/kb_scan/report/kb_scan-" + item.id() + ".html");
        verify(archiveService).markRunning(ARCHIVE_ID);
        verify(archiveService).markSucceeded(eq(ARCHIVE_ID), eq(ARTIFACT_ID), eq(7L), eq("sha"), any());
        verify(context).log(TaskLogType.TOOL, "归档包已生成，归档项数量：1");
        verify(context).progress(95, "归档完成");
    }

    @Test
    void preservesValidArtifactFilename() throws Exception {
        ProjectArchiveView archive = archive();
        UUID sourceArtifactId = UUID.randomUUID();
        ArchiveCandidateView candidate = candidate();
        ProjectArchiveItemView item = item(candidate, List.of(
                new ArchiveArtifactRef("JSON", sourceArtifactId, "RAW_RESULT", "application/json", "report.json")));
        when(archiveService.requireInternalByTaskId(TASK_ID)).thenReturn(archive);
        when(context.input(ProjectArchiveInput.class)).thenReturn(new ProjectArchiveInput(PROJECT_ID, REVISION_ID));
        when(archiveService.activeCandidates(PROJECT_ID, REVISION_ID)).thenReturn(List.of(candidate));
        when(archiveService.createItem(ARCHIVE_ID, candidate)).thenReturn(item);
        when(storedArtifactService.download(sourceArtifactId)).thenReturn(resource(sourceArtifactId, "{}"));
        when(storedArtifactService.store(any(), eq(context))).thenReturn(storedArtifact());

        handler.handle(context);

        ArgumentCaptor<StoredArtifactCreateCommand> command = ArgumentCaptor.forClass(StoredArtifactCreateCommand.class);
        verify(storedArtifactService).store(command.capture(), eq(context));
        assertThat(zipEntries(command.getValue().content())).contains("items/kb_scan/report/report.json");
    }

    @Test
    void rejectsMismatchedTaskInputBeforeChangingState() {
        when(archiveService.requireInternalByTaskId(TASK_ID)).thenReturn(archive());
        when(context.input(ProjectArchiveInput.class)).thenReturn(
                new ProjectArchiveInput(UUID.randomUUID(), REVISION_ID));

        assertThatThrownBy(() -> handler.handle(context))
                .isInstanceOf(TaskExecutionException.class)
                .extracting(ex -> ((TaskExecutionException) ex).errorCode())
                .isEqualTo(TaskErrorCode.PROJECT_MISMATCH);
        verify(archiveService, never()).markRunning(any());
    }

    @Test
    void rejectsMismatchedSourceRevisionEvenWhenProjectMatches() {
        when(archiveService.requireInternalByTaskId(TASK_ID)).thenReturn(archive());
        when(context.input(ProjectArchiveInput.class)).thenReturn(
                new ProjectArchiveInput(PROJECT_ID, UUID.randomUUID()));

        assertThatThrownBy(() -> handler.handle(context))
                .isInstanceOf(TaskExecutionException.class)
                .extracting(ex -> ((TaskExecutionException) ex).errorCode())
                .isEqualTo(TaskErrorCode.PROJECT_MISMATCH);
        verify(archiveService, never()).markRunning(any());
    }

    @Test
    void failsWhenThereAreNoActiveCandidates() {
        when(archiveService.requireInternalByTaskId(TASK_ID)).thenReturn(archive());
        when(context.input(ProjectArchiveInput.class)).thenReturn(new ProjectArchiveInput(PROJECT_ID, REVISION_ID));
        when(archiveService.activeCandidates(PROJECT_ID, REVISION_ID)).thenReturn(List.of());

        assertThatThrownBy(() -> handler.handle(context))
                .isInstanceOf(TaskExecutionException.class)
                .extracting(ex -> ((TaskExecutionException) ex).errorCode())
                .isEqualTo(TaskErrorCode.INPUT_INVALID);
        verify(archiveService).markFailed(eq(ARCHIVE_ID), eq(Map.of(
                "errorCode", "ARCHIVE_NO_CANDIDATES", "message", "当前源码版本没有可归档内容")));
        verify(storedArtifactService, never()).store(any(), any());
    }

    @Test
    void convertsUnexpectedFailureAndPersistsSafeMessage() {
        when(archiveService.requireInternalByTaskId(TASK_ID)).thenReturn(archive());
        when(context.input(ProjectArchiveInput.class)).thenReturn(new ProjectArchiveInput(PROJECT_ID, REVISION_ID));
        when(archiveService.activeCandidates(PROJECT_ID, REVISION_ID)).thenThrow(new IllegalStateException());

        assertThatThrownBy(() -> handler.handle(context))
                .isInstanceOf(TaskExecutionException.class)
                .extracting(ex -> ((TaskExecutionException) ex).errorCode())
                .isEqualTo(TaskErrorCode.HANDLER_FAILED);
        verify(archiveService).markFailed(ARCHIVE_ID, Map.of(
                "errorCode", TaskErrorCode.HANDLER_FAILED, "message", "项目归档失败"));
    }

    @Test
    void propagatesZipReadFailureWithoutStoringPartialArchive() throws Exception {
        ProjectArchiveView archive = archive();
        UUID sourceArtifactId = UUID.randomUUID();
        ArchiveCandidateView candidate = candidate();
        ProjectArchiveItemView item = item(candidate, List.of(
                new ArchiveArtifactRef("JSON", sourceArtifactId, "RAW_RESULT", "application/json", null)));
        Resource broken = org.mockito.Mockito.mock(Resource.class);
        when(broken.getContentAsByteArray()).thenThrow(new IOException("broken"));
        when(archiveService.requireInternalByTaskId(TASK_ID)).thenReturn(archive);
        when(context.input(ProjectArchiveInput.class)).thenReturn(new ProjectArchiveInput(PROJECT_ID, REVISION_ID));
        when(archiveService.activeCandidates(PROJECT_ID, REVISION_ID)).thenReturn(List.of(candidate));
        when(archiveService.createItem(ARCHIVE_ID, candidate)).thenReturn(item);
        when(storedArtifactService.download(sourceArtifactId)).thenReturn(
                new StoredArtifactResource(storedArtifact(), broken));

        assertThatThrownBy(() -> handler.handle(context))
                .isInstanceOf(TaskExecutionException.class)
                .hasMessage("归档包生成失败")
                .hasCauseInstanceOf(IOException.class);
        verify(storedArtifactService, never()).store(any(), any());
    }

    @Test
    void sanitizesEveryUnsafeArchiveFilenameShapeAndFailureMessage() {
        ArchiveCandidateView candidate = candidate();
        ProjectArchiveItemView item = item(candidate, List.of());
        for (String filename : List.of(" ", "folder/file.json", "folder\\file.json", "unsafe..json")) {
            ArchiveArtifactRef ref = new ArchiveArtifactRef(
                    "JSON", UUID.randomUUID(), "RAW_RESULT", "application/json", filename);
            String entry = ReflectionTestUtils.invokeMethod(handler, "entryName", item, ref);
            assertThat(entry).endsWith("kb_scan-" + item.id() + ".json");
        }
        assertThat((String) ReflectionTestUtils.invokeMethod(handler, "safeMessage", new IllegalStateException(" ")))
                .isEqualTo("项目归档失败");
        assertThat((String) ReflectionTestUtils.invokeMethod(handler, "safeMessage", new IllegalStateException("disk full")))
                .isEqualTo("disk full");
    }

    private static ProjectArchiveView archive() {
        return new ProjectArchiveView(ARCHIVE_ID, PROJECT_ID, REVISION_ID, TASK_ID, null, "archive",
                TaskStatus.PENDING, Map.of(), null, null, UUID.randomUUID(), NOW, NOW);
    }

    private static ArchiveCandidateView candidate() {
        return new ArchiveCandidateView(UUID.randomUUID(), PROJECT_ID, REVISION_ID, ArchiveNodeType.KB_SCAN,
                ArchiveCandidateType.REPORT, "kb-report", "KB_SCAN", UUID.randomUUID(), "KB report",
                Map.of("count", 1), List.of(), ArchiveCandidateStatus.ACTIVE, NOW, NOW);
    }

    private static ProjectArchiveItemView item(ArchiveCandidateView candidate, List<ArchiveArtifactRef> refs) {
        return new ProjectArchiveItemView(UUID.randomUUID(), ARCHIVE_ID, candidate.id(), candidate.nodeType(),
                candidate.candidateType(), candidate.candidateKey(), candidate.resourceType(), candidate.resourceId(),
                candidate.title(), refs, Map.of("count", 1), NOW);
    }

    private static StoredArtifactView storedArtifact() {
        return new StoredArtifactView(ARTIFACT_ID, PROJECT_ID, TASK_ID, StoredArtifactOwnerType.ARCHIVE,
                ARCHIVE_ID, "PROJECT_ARCHIVE_ZIP", "bucket", "key", "application/zip", 7L, "sha", Map.of(), NOW);
    }

    private static StoredArtifactResource resource(UUID artifactId, String content) {
        StoredArtifactView artifact = new StoredArtifactView(artifactId, PROJECT_ID, TASK_ID,
                StoredArtifactOwnerType.ARCHIVE, ARCHIVE_ID, "SOURCE", "bucket", "source-key",
                "application/json", content.length(), "source-sha", Map.of(), NOW);
        return new StoredArtifactResource(artifact, new ByteArrayResource(content.getBytes(java.nio.charset.StandardCharsets.UTF_8)));
    }

    private static TaskView task() {
        return new TaskView(TASK_ID, PROJECT_ID, RvPortTaskTypes.ARCHIVE_PROJECT, TaskStatus.RUNNING, 0, "running",
                UUID.randomUUID(), NOW, NOW, NOW, null, 300, null, null, 0);
    }

    private static List<String> zipEntries(byte[] content) throws IOException {
        List<String> names = new ArrayList<>();
        try (ZipInputStream zip = new ZipInputStream(new ByteArrayInputStream(content))) {
            ZipEntry entry;
            while ((entry = zip.getNextEntry()) != null) {
                names.add(entry.getName());
            }
        }
        return names;
    }
}
