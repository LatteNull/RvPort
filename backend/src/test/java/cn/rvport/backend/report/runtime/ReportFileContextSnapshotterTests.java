package cn.rvport.backend.report.runtime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.artifact.StoredArtifactService;
import cn.rvport.backend.artifact.StoredArtifactView;
import cn.rvport.backend.migration.MigrationInputRefView;
import cn.rvport.backend.migration.MigrationInputSourceType;
import cn.rvport.backend.migration.MigrationInputStatus;
import cn.rvport.backend.report.ReportFileContextView;
import cn.rvport.backend.report.ReportInputProjection;
import cn.rvport.backend.report.ReportOrganizationRepository;
import cn.rvport.backend.report.ReportRepository;
import cn.rvport.backend.report.ReportType;
import cn.rvport.backend.report.ReportView;
import cn.rvport.backend.source.SourceRevisionType;
import cn.rvport.backend.source.SourceRevisionView;
import cn.rvport.backend.task.TaskStatus;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.mockito.ArgumentCaptor;

class ReportFileContextSnapshotterTests {

    private final cn.rvport.backend.worker.TaskExecutionContext execution = mock(cn.rvport.backend.worker.TaskExecutionContext.class);

    @org.junit.jupiter.api.BeforeEach
    void allowPublication() {
        when(execution.publish(any())).thenAnswer(call -> ((java.util.function.Supplier<?>) call.getArgument(0)).get());
    }

    @TempDir
    Path root;

    @Test
    void lostPublicationIsNotDowngradedToUnavailableContext() throws Exception {
        Files.writeString(root.resolve("file.c"), "int value;\n");
        StoredArtifactService artifacts = mock(StoredArtifactService.class);
        ReportOrganizationRepository repository = mock(ReportOrganizationRepository.class);
        when(artifacts.store(any(), any())).thenThrow(new cn.rvport.backend.worker.TaskAttemptLostException());
        org.assertj.core.api.Assertions.assertThatThrownBy(() ->
                new ReportFileContextSnapshotter(artifacts, repository).capture(
                        report(), revision(root), List.of(snapshot("file.c", "file")), execution))
                .isInstanceOf(cn.rvport.backend.worker.TaskAttemptLostException.class);
        org.mockito.Mockito.verifyNoInteractions(repository);
    }

    @Test
    void storesUtf8SourceAndPersistsImmutableMetadata() throws Exception {
        Files.createDirectories(root.resolve("src"));
        Files.writeString(root.resolve("src/main.c"), "int main(void) {\n  return 0;\n}\n");
        StoredArtifactService artifacts = mock(StoredArtifactService.class);
        ReportOrganizationRepository repository = mock(ReportOrganizationRepository.class);
        UUID artifactId = UUID.randomUUID();
        when(artifacts.store(any(), any())).thenReturn(mockArtifact(artifactId));
        ReportFileContextSnapshotter snapshotter = new ReportFileContextSnapshotter(artifacts, repository);

        Map<String, String> hashes = snapshotter.capture(report(), revision(root), List.of(snapshot("src/main.c", "file-key")), execution);

        assertThat(hashes.get("file-key")).hasSize(64);
        ArgumentCaptor<ReportFileContextView> context = ArgumentCaptor.forClass(ReportFileContextView.class);
        verify(repository).upsertFileContext(context.capture());
        assertThat(context.getValue().contextAvailable()).isTrue();
        assertThat(context.getValue().artifactId()).isEqualTo(artifactId);
        assertThat(context.getValue().totalLines()).isEqualTo(4);
    }

    @Test
    void degradesMissingBinaryAndUnsafeFilesWithoutThrowing() throws Exception {
        Files.write(root.resolve("binary.bin"), new byte[]{1, 0, 2});
        StoredArtifactService artifacts = mock(StoredArtifactService.class);
        ReportOrganizationRepository repository = mock(ReportOrganizationRepository.class);
        ReportFileContextSnapshotter snapshotter = new ReportFileContextSnapshotter(artifacts, repository);

        assertThat(snapshotter.capture(report(), revision(root), List.of(snapshot("missing.c", "missing")), execution)).isEmpty();
        assertThat(snapshotter.capture(report(), revision(root), List.of(snapshot("binary.bin", "binary")), execution)).isEmpty();
        assertThat(snapshotter.capture(report(), revision(root), List.of(snapshot("../secret.c", "unsafe")), execution)).isEmpty();

        ArgumentCaptor<ReportFileContextView> context = ArgumentCaptor.forClass(ReportFileContextView.class);
        verify(repository, org.mockito.Mockito.times(3)).upsertFileContext(context.capture());
        assertThat(context.getAllValues()).extracting(ReportFileContextView::unavailableReason)
                .containsExactly("SOURCE_FILE_MISSING", "BINARY_FILE", "PATH_UNSAFE");
    }

    @Test
    void degradesUnavailableRevisionInvalidUtf8OversizedAndStorageFailures() throws Exception {
        Files.write(root.resolve("invalid.c"), new byte[]{(byte) 0xc3, (byte) 0x28});
        byte[] oversized = new byte[(int) ReportFileContextSnapshotter.MAX_SOURCE_FILE_BYTES + 1];
        java.util.Arrays.fill(oversized, (byte) 'x');
        Files.write(root.resolve("large.c"), oversized);
        Files.writeString(root.resolve("store-fails.c"), "int value;\n");
        StoredArtifactService artifacts = mock(StoredArtifactService.class);
        ReportOrganizationRepository repository = mock(ReportOrganizationRepository.class);
        when(artifacts.store(any(), any())).thenThrow(new IllegalStateException("storage unavailable"));
        ReportFileContextSnapshotter snapshotter = new ReportFileContextSnapshotter(artifacts, repository);

        assertThat(snapshotter.capture(report(), null, List.of(snapshot("missing.c", "no-revision")), execution)).isEmpty();
        assertThat(snapshotter.capture(report(), revision(root), List.of(snapshot("invalid.c", "invalid")), execution)).isEmpty();
        assertThat(snapshotter.capture(report(), revision(root), List.of(snapshot("large.c", "large")), execution)).isEmpty();
        assertThat(snapshotter.capture(report(), revision(root), List.of(snapshot("store-fails.c", "store-fails")), execution)).isEmpty();

        ArgumentCaptor<ReportFileContextView> context = ArgumentCaptor.forClass(ReportFileContextView.class);
        verify(repository, org.mockito.Mockito.times(4)).upsertFileContext(context.capture());
        assertThat(context.getAllValues()).extracting(ReportFileContextView::unavailableReason)
                .containsExactly("SOURCE_REVISION_UNAVAILABLE", "INVALID_UTF8", "FILE_TOO_LARGE", "CONTEXT_SNAPSHOT_FAILED");
    }

    @Test
    void ignoresNonFileProjectionsAndDeduplicatesFiles() throws Exception {
        Files.writeString(root.resolve("empty.c"), "");
        StoredArtifactService artifacts = mock(StoredArtifactService.class);
        ReportOrganizationRepository repository = mock(ReportOrganizationRepository.class);
        when(artifacts.store(any(), any())).thenReturn(mockArtifact(UUID.randomUUID()));
        ReportFileContextSnapshotter snapshotter = new ReportFileContextSnapshotter(artifacts, repository);
        ReportRepository.ReportInputSnapshot valid = snapshot("empty.c", "same");
        ReportRepository.ReportInputSnapshot noProjection = new ReportRepository.ReportInputSnapshot(valid.ref(), Map.of(), null);
        ReportRepository.ReportInputSnapshot noPath = new ReportRepository.ReportInputSnapshot(valid.ref(), Map.of(),
                ReportInputProjection.none("DEPENDENCY_RESULT", "INFO"));
        ReportInputProjection noFileKeyProjection = new ReportInputProjection("KB_FINDING", "LOW", "module", "module",
                "DIRECTORY", "LOW", List.of(), null, "empty.c", "TYPE", 1, 1, null, null, null, null, true);
        ReportRepository.ReportInputSnapshot noFileKey = new ReportRepository.ReportInputSnapshot(
                valid.ref(), Map.of(), noFileKeyProjection);

        Map<String, String> hashes = snapshotter.capture(report(), revision(root), List.of(noProjection, noPath, noFileKey, valid, valid), execution);

        assertThat(hashes).containsOnlyKeys("same");
        verify(artifacts).store(any(), any());
        verify(repository).upsertFileContext(any());
    }

    @Test
    void rejectsAbsolutePathsAndBlankWorkingCopies() {
        StoredArtifactService artifacts = mock(StoredArtifactService.class);
        ReportOrganizationRepository repository = mock(ReportOrganizationRepository.class);
        ReportFileContextSnapshotter snapshotter = new ReportFileContextSnapshotter(artifacts, repository);
        SourceRevisionView blankRevision = new SourceRevisionView(UUID.randomUUID(), UUID.randomUUID(), SourceRevisionType.GIT,
                "v1", null, null, null, null, null, " ", null, true, UUID.randomUUID(), OffsetDateTime.now());

        assertThat(snapshotter.capture(report(), revision(root),
                List.of(snapshot(root.resolve("empty.c").toAbsolutePath().toString(), "absolute")), execution)).isEmpty();
        assertThat(snapshotter.capture(report(), blankRevision, List.of(snapshot("empty.c", "blank")), execution)).isEmpty();

        ArgumentCaptor<ReportFileContextView> context = ArgumentCaptor.forClass(ReportFileContextView.class);
        verify(repository, org.mockito.Mockito.times(2)).upsertFileContext(context.capture());
        assertThat(context.getAllValues()).extracting(ReportFileContextView::unavailableReason)
                .containsExactly("PATH_UNSAFE", "SOURCE_REVISION_UNAVAILABLE");
    }

    private ReportRepository.ReportInputSnapshot snapshot(String path, String fileKey) {
        MigrationInputRefView ref = new MigrationInputRefView(UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(),
                "issue", MigrationInputSourceType.KB_FINDING, UUID.randomUUID(), "HIGH", path, "fix", "rule", path,
                "symbol", "anchor", "fingerprint", MigrationInputStatus.CONFIRMED, null, OffsetDateTime.now(), OffsetDateTime.now());
        ReportInputProjection projection = new ReportInputProjection("KB_FINDING", "HIGH", "module", "module", "DIRECTORY", "LOW",
                List.of(), fileKey, path, "TYPE", 1, 1, null, null, "symbol", null, true);
        return new ReportRepository.ReportInputSnapshot(ref, Map.of(), projection);
    }

    private ReportView report() {
        UUID revisionId = UUID.randomUUID();
        return new ReportView(UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), revisionId, ReportType.EVALUATION,
                TaskStatus.RUNNING, "report", Map.of(), null, UUID.randomUUID(), null, OffsetDateTime.now());
    }

    private SourceRevisionView revision(Path sourceRoot) {
        return new SourceRevisionView(UUID.randomUUID(), UUID.randomUUID(), SourceRevisionType.GIT, "v1", null, null,
                null, null, null, sourceRoot.toString(), null, true, UUID.randomUUID(), OffsetDateTime.now());
    }

    private StoredArtifactView mockArtifact(UUID artifactId) {
        return new StoredArtifactView(artifactId, UUID.randomUUID(), UUID.randomUUID(), null, UUID.randomUUID(),
                "SOURCE_CONTEXT", "bucket", "key", "text/plain", 10, "hash", Map.of(), OffsetDateTime.now());
    }
}
