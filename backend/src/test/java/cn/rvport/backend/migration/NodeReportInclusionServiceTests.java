package cn.rvport.backend.migration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.when;

import cn.rvport.backend.report.ReportRepository;
import cn.rvport.backend.report.ReportType;
import cn.rvport.backend.report.ReportView;
import cn.rvport.backend.task.TaskStatus;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class NodeReportInclusionServiceTests {

    @Mock
    private MigrationInputRepository migrationInputRepository;

    @Mock
    private ReportRepository reportRepository;

    @Test
    void returnsEmptyStateWhenMigrationInputRefDoesNotExist() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID sourceRefId = UUID.randomUUID();
        when(migrationInputRepository.findBySourceRefs(projectId, sourceRevisionId, MigrationInputSourceType.KB_FINDING, List.of(sourceRefId)))
                .thenReturn(Map.of());
        when(reportRepository.latestSucceeded(projectId, sourceRevisionId)).thenReturn(java.util.Optional.empty());

        NodeReportInclusionState state = service().state(projectId, sourceRevisionId, MigrationInputSourceType.KB_FINDING, sourceRefId);

        assertThat(state.migrationInputRefId()).isNull();
        assertThat(state.migrationInputStatus()).isNull();
        assertThat(state.confirmedForNextReport()).isFalse();
        assertThat(state.includedInLatestReport()).isFalse();
        assertThat(state.latestReportId()).isNull();
    }

    @Test
    void marksConfirmedRefIncludedWhenLatestReportContainsIt() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID sourceRefId = UUID.randomUUID();
        UUID refId = UUID.randomUUID();
        UUID reportId = UUID.randomUUID();
        MigrationInputRefView ref = ref(projectId, sourceRevisionId, sourceRefId, refId, MigrationInputStatus.CONFIRMED);
        when(migrationInputRepository.findBySourceRefs(projectId, sourceRevisionId, MigrationInputSourceType.KB_FINDING, List.of(sourceRefId)))
                .thenReturn(Map.of(sourceRefId, ref));
        when(reportRepository.latestSucceeded(projectId, sourceRevisionId)).thenReturn(java.util.Optional.of(report(reportId, projectId, sourceRevisionId)));
        when(reportRepository.listMigrationInputIds(reportId)).thenReturn(List.of(refId));

        NodeReportInclusionState state = service().state(projectId, sourceRevisionId, MigrationInputSourceType.KB_FINDING, sourceRefId);

        assertThat(state.migrationInputRefId()).isEqualTo(refId);
        assertThat(state.migrationInputStatus()).isEqualTo(MigrationInputStatus.CONFIRMED);
        assertThat(state.confirmedForNextReport()).isTrue();
        assertThat(state.includedInLatestReport()).isTrue();
        assertThat(state.latestReportId()).isEqualTo(reportId);
    }

    @Test
    void keepsCandidateOrExcludedRefOutOfLatestReportByDefault() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID sourceRefId = UUID.randomUUID();
        UUID refId = UUID.randomUUID();
        MigrationInputRefView ref = ref(projectId, sourceRevisionId, sourceRefId, refId, MigrationInputStatus.CANDIDATE);
        when(migrationInputRepository.findBySourceRefs(projectId, sourceRevisionId, MigrationInputSourceType.DEPENDENCY_RESULT, List.of(sourceRefId)))
                .thenReturn(Map.of(sourceRefId, ref));
        when(reportRepository.latestSucceeded(projectId, sourceRevisionId)).thenReturn(java.util.Optional.empty());

        NodeReportInclusionState state = service().state(projectId, sourceRevisionId, MigrationInputSourceType.DEPENDENCY_RESULT, sourceRefId);

        assertThat(state.migrationInputRefId()).isEqualTo(refId);
        assertThat(state.migrationInputStatus()).isEqualTo(MigrationInputStatus.CANDIDATE);
        assertThat(state.confirmedForNextReport()).isFalse();
        assertThat(state.includedInLatestReport()).isFalse();
        assertThat(state.latestReportId()).isNull();
    }

    @Test
    void toleratesNullRepositoryCollectionsAndEmptyRequests() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID sourceRefId = UUID.randomUUID();
        when(migrationInputRepository.findBySourceRefs(projectId, sourceRevisionId,
                MigrationInputSourceType.KB_FINDING, List.of(sourceRefId))).thenReturn(null);
        ReportView report = report(UUID.randomUUID(), projectId, sourceRevisionId);
        when(reportRepository.latestSucceeded(projectId, sourceRevisionId)).thenReturn(java.util.Optional.of(report));
        when(reportRepository.listMigrationInputIds(report.id())).thenReturn(null);

        assertThat(service().states(projectId, sourceRevisionId, MigrationInputSourceType.KB_FINDING, null)).isEmpty();
        assertThat(service().states(projectId, sourceRevisionId, MigrationInputSourceType.KB_FINDING, List.of())).isEmpty();
        assertThat(service().state(projectId, sourceRevisionId, MigrationInputSourceType.KB_FINDING, sourceRefId))
                .isEqualTo(NodeReportInclusionState.empty());
    }

    @Test
    void distinguishesConfirmedButNotYetArchivedFromIncludedCandidate() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID confirmedSourceId = UUID.randomUUID();
        UUID candidateSourceId = UUID.randomUUID();
        MigrationInputRefView confirmed = ref(projectId, sourceRevisionId, confirmedSourceId,
                UUID.randomUUID(), MigrationInputStatus.CONFIRMED);
        MigrationInputRefView candidate = ref(projectId, sourceRevisionId, candidateSourceId,
                UUID.randomUUID(), MigrationInputStatus.CANDIDATE);
        List<UUID> ids = List.of(confirmedSourceId, candidateSourceId);
        when(migrationInputRepository.findBySourceRefs(projectId, sourceRevisionId,
                MigrationInputSourceType.KB_FINDING, ids)).thenReturn(Map.of(
                confirmedSourceId, confirmed, candidateSourceId, candidate));
        ReportView report = report(UUID.randomUUID(), projectId, sourceRevisionId);
        when(reportRepository.latestSucceeded(projectId, sourceRevisionId)).thenReturn(java.util.Optional.of(report));
        when(reportRepository.listMigrationInputIds(report.id())).thenReturn(List.of(candidate.id()));

        Map<UUID, NodeReportInclusionState> states = service().states(
                projectId, sourceRevisionId, MigrationInputSourceType.KB_FINDING, ids);

        assertThat(states.get(confirmedSourceId).confirmedForNextReport()).isTrue();
        assertThat(states.get(confirmedSourceId).includedInLatestReport()).isFalse();
        assertThat(states.get(candidateSourceId).confirmedForNextReport()).isFalse();
        assertThat(states.get(candidateSourceId).includedInLatestReport()).isTrue();
        assertThat(states.get(candidateSourceId).latestReportId()).isEqualTo(report.id());
    }

    private NodeReportInclusionService service() {
        return new NodeReportInclusionService(migrationInputRepository, reportRepository);
    }

    private MigrationInputRefView ref(UUID projectId, UUID sourceRevisionId, UUID sourceRefId, UUID refId, MigrationInputStatus status) {
        OffsetDateTime now = OffsetDateTime.now();
        return new MigrationInputRefView(
                refId,
                UUID.randomUUID(),
                projectId,
                sourceRevisionId,
                "issue",
                MigrationInputSourceType.KB_FINDING,
                sourceRefId,
                "HIGH",
                "src/main.c:10",
                "fix it",
                "rule",
                "src/main.c",
                "symbol",
                "anchor",
                "fingerprint",
                status,
                null,
                now,
                now
        );
    }

    private ReportView report(UUID reportId, UUID projectId, UUID sourceRevisionId) {
        OffsetDateTime now = OffsetDateTime.now();
        return new ReportView(
                reportId,
                projectId,
                UUID.randomUUID(),
                sourceRevisionId,
                ReportType.EVALUATION,
                TaskStatus.SUCCEEDED,
                "report",
                Map.of(),
                "HIGH",
                UUID.randomUUID(),
                now,
                now
        );
    }
}
