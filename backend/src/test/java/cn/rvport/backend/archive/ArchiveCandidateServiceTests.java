package cn.rvport.backend.archive;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.common.error.ApiException;
import java.time.OffsetDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class ArchiveCandidateServiceTests {

    @Mock
    private ArchiveCandidateRepository repository;

    @Test
    void upsertsSafeCandidate() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        ArchiveCandidateUpsertCommand command = command(projectId, revisionId, Map.of("riskLevel", "HIGH"), List.of(
                new ArchiveArtifactRef("HTML", UUID.randomUUID(), "REPORT_HTML", "text/html", "report.html")
        ));
        ArchiveCandidateView view = new ArchiveCandidateView(
                UUID.randomUUID(),
                projectId,
                revisionId,
                ArchiveNodeType.MIGRATION_REPORT,
                ArchiveCandidateType.REPORT,
                "migration-report",
                "MIGRATION_REPORT",
                UUID.randomUUID(),
                "迁移报告",
                new LinkedHashMap<>(command.summary()),
                command.artifactRefs(),
                ArchiveCandidateStatus.ACTIVE,
                OffsetDateTime.now(),
                OffsetDateTime.now()
        );
        when(repository.upsert(command)).thenReturn(view);

        assertThat(service().upsert(command)).isEqualTo(view);
        verify(repository).upsert(command);
    }

    @Test
    void rejectsSensitiveSummaryKeysAndServerPaths() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();

        assertThatThrownBy(() -> service().upsert(command(projectId, revisionId, Map.of("objectKey", "a/b"), List.of())))
                .isInstanceOf(ApiException.class)
                .extracting("code")
                .isEqualTo("ARCHIVE_CANDIDATE_UNSAFE_CONTENT");
        assertThatThrownBy(() -> service().upsert(command(projectId, revisionId, Map.of("privateKey", "value"), List.of())))
                .isInstanceOf(ApiException.class)
                .extracting("code")
                .isEqualTo("ARCHIVE_CANDIDATE_UNSAFE_CONTENT");
        assertThatThrownBy(() -> service().upsert(command(projectId, revisionId, Map.of("location", "/srv/rvport/data"), List.of())))
                .isInstanceOf(ApiException.class)
                .extracting("code")
                .isEqualTo("ARCHIVE_CANDIDATE_UNSAFE_CONTENT");
        assertThatThrownBy(() -> service().upsert(command(projectId, revisionId, Map.of("location", "C:\\rvport\\data"), List.of())))
                .isInstanceOf(ApiException.class)
                .extracting("code")
                .isEqualTo("ARCHIVE_CANDIDATE_UNSAFE_CONTENT");
        assertThatThrownBy(() -> service().upsert(command(projectId, revisionId, Map.of("paths", List.of("src/../secret.c")), List.of())))
                .isInstanceOf(ApiException.class)
                .extracting("code")
                .isEqualTo("ARCHIVE_CANDIDATE_UNSAFE_CONTENT");
    }

    @Test
    void acceptsPathKeysWithEmptyOrSafeRelativeValues() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        Map<String, Object> summary = Map.of(
                "paths", List.of(),
                "scope", Map.of("filePath", "src/main.c", "nestedPaths", List.of("include/compat.h"))
        );
        ArchiveCandidateUpsertCommand command = command(projectId, revisionId, summary, List.of());
        ArchiveCandidateView view = new ArchiveCandidateView(
                UUID.randomUUID(), projectId, revisionId, ArchiveNodeType.MIGRATION_REPORT,
                ArchiveCandidateType.REPORT, "migration-report", "MIGRATION_REPORT", UUID.randomUUID(),
                "迁移报告", summary, List.of(), ArchiveCandidateStatus.ACTIVE,
                OffsetDateTime.now(), OffsetDateTime.now());
        when(repository.upsert(command)).thenReturn(view);

        assertThat(service().upsert(command)).isEqualTo(view);
        verify(repository).upsert(command);
    }

    @Test
    void listsNoActiveCandidatesAsEmptyResult() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        when(repository.listActive(projectId, revisionId)).thenReturn(List.of());

        assertThat(service().listActive(projectId, revisionId)).isEmpty();
    }

    @Test
    void rejectsEachMissingRequiredCandidateField() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        UUID resourceId = UUID.randomUUID();
        List<ArchiveCandidateUpsertCommand> invalid = List.of(
                rawCommand(null, revisionId, ArchiveNodeType.KB_SCAN, ArchiveCandidateType.REPORT,
                        "key", "KB_SCAN", resourceId, "title", Map.of(), List.of()),
                rawCommand(projectId, null, ArchiveNodeType.KB_SCAN, ArchiveCandidateType.REPORT,
                        "key", "KB_SCAN", resourceId, "title", Map.of(), List.of()),
                rawCommand(projectId, revisionId, null, ArchiveCandidateType.REPORT,
                        "key", "KB_SCAN", resourceId, "title", Map.of(), List.of()),
                rawCommand(projectId, revisionId, ArchiveNodeType.KB_SCAN, null,
                        "key", "KB_SCAN", resourceId, "title", Map.of(), List.of()),
                rawCommand(projectId, revisionId, ArchiveNodeType.KB_SCAN, ArchiveCandidateType.REPORT,
                        " ", "KB_SCAN", resourceId, "title", Map.of(), List.of()),
                rawCommand(projectId, revisionId, ArchiveNodeType.KB_SCAN, ArchiveCandidateType.REPORT,
                        "key", " ", resourceId, "title", Map.of(), List.of()),
                rawCommand(projectId, revisionId, ArchiveNodeType.KB_SCAN, ArchiveCandidateType.REPORT,
                        "key", "KB_SCAN", resourceId, " ", Map.of(), List.of())
        );

        invalid.forEach(command -> assertThatThrownBy(() -> service().upsert(command))
                .isInstanceOfSatisfying(ApiException.class,
                        failure -> assertThat(failure.code()).isEqualTo("ARCHIVE_CANDIDATE_INVALID")));
    }

    @Test
    void acceptsNullOptionalContentAndSafeArtifactMetadata() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        ArchiveCandidateUpsertCommand command = command(projectId, revisionId, null, List.of(
                new ArchiveArtifactRef(null, UUID.randomUUID(), " ", "application/json", "report.json")
        ));
        when(repository.upsert(command)).thenReturn(null);

        assertThat(service().upsert(command)).isNull();

        ArchiveCandidateUpsertCommand noArtifacts = command(projectId, revisionId, Map.of("note", " "), null);
        when(repository.upsert(noArtifacts)).thenReturn(null);
        assertThat(service().upsert(noArtifacts)).isNull();
    }

    @Test
    void rejectsSensitiveTextInsideArtifactReference() {
        ArchiveCandidateUpsertCommand command = command(UUID.randomUUID(), UUID.randomUUID(), Map.of(), List.of(
                new ArchiveArtifactRef("JSON", UUID.randomUUID(), "REPORT", "text/plain", "token secret")
        ));

        assertThatThrownBy(() -> service().upsert(command))
                .isInstanceOfSatisfying(ApiException.class,
                        failure -> assertThat(failure.code()).isEqualTo("ARCHIVE_CANDIDATE_UNSAFE_CONTENT"));
    }

    private ArchiveCandidateUpsertCommand rawCommand(
            UUID projectId, UUID revisionId, ArchiveNodeType nodeType, ArchiveCandidateType candidateType,
            String candidateKey, String resourceType, UUID resourceId, String title,
            Map<String, ?> summary, List<ArchiveArtifactRef> refs
    ) {
        return new ArchiveCandidateUpsertCommand(projectId, revisionId, nodeType, candidateType, candidateKey,
                resourceType, resourceId, title, summary, refs);
    }

    private ArchiveCandidateService service() {
        return new ArchiveCandidateService(repository);
    }

    private ArchiveCandidateUpsertCommand command(
            UUID projectId,
            UUID revisionId,
            Map<String, Object> summary,
            List<ArchiveArtifactRef> artifactRefs
    ) {
        return new ArchiveCandidateUpsertCommand(
                projectId,
                revisionId,
                ArchiveNodeType.MIGRATION_REPORT,
                ArchiveCandidateType.REPORT,
                "migration-report",
                "MIGRATION_REPORT",
                UUID.randomUUID(),
                "迁移报告",
                summary,
                artifactRefs
        );
    }
}
