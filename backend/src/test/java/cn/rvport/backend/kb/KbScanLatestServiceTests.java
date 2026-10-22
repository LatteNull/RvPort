package cn.rvport.backend.kb;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.audit.AuditLogService;
import cn.rvport.backend.artifact.StoredArtifactService;
import cn.rvport.backend.config.RvPortProperties;
import cn.rvport.backend.kb.ai.KbAiExtensionRepository;
import cn.rvport.backend.migration.NodeReportInclusionService;
import cn.rvport.backend.project.ProjectAccessService;
import cn.rvport.backend.source.SourceRepository;
import cn.rvport.backend.task.TaskRepository;
import cn.rvport.backend.task.TaskService;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.task.TaskView;
import cn.rvport.backend.workflow.DomainLatestFreshness;
import cn.rvport.backend.workflow.DomainLatestResponse;
import cn.rvport.backend.workflow.ProjectContextService;
import cn.rvport.backend.workflow.ProjectContextSnapshot;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class KbScanLatestServiceTests {

    @Mock
    private KbScanRepository kbScanRepository;
    @Mock
    private SourceRepository sourceRepository;
    @Mock
    private ProjectAccessService projectAccessService;
    @Mock
    private TaskService taskService;
    @Mock
    private TaskRepository taskRepository;
    @Mock
    private ProjectContextService projectContextService;
    @Mock
    private AuditLogService auditLogService;
    @Mock
    private StoredArtifactService storedArtifactService;
    @Mock
    private NodeReportInclusionService nodeReportInclusionService;
    @Mock
    private KbAiExtensionRepository kbAiExtensionRepository;

    @Test
    void latestReturnsCurrentFailedRunWithoutFallingBack() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID runId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        KbScanView failed = run(projectId, runId, taskId, sourceRevisionId, TaskStatus.FAILED);
        when(projectContextService.snapshot(projectId)).thenReturn(new ProjectContextSnapshot(sourceRevisionId, 9L));
        when(kbScanRepository.findLatestRunBySourceRevision(projectId, sourceRevisionId)).thenReturn(Optional.of(failed));
        when(taskRepository.findById(taskId)).thenReturn(Optional.of(task(projectId, taskId, TaskStatus.FAILED)));

        DomainLatestResponse<KbScanResponse> response = service().latest(projectId, UUID.randomUUID(), false);

        assertThat(response.freshness()).isEqualTo(DomainLatestFreshness.CURRENT);
        assertThat(response.execution().status()).isEqualTo(TaskStatus.FAILED);
        assertThat(response.result().id()).isEqualTo(runId);
    }

    @Test
    void latestReturnsEmptyWhenCurrentSourceMissing() {
        UUID projectId = UUID.randomUUID();
        when(projectContextService.snapshot(projectId)).thenReturn(new ProjectContextSnapshot(null, 1L));

        DomainLatestResponse<KbScanResponse> response = service().latest(projectId, UUID.randomUUID(), false);

        assertThat(response.freshness()).isEqualTo(DomainLatestFreshness.EMPTY);
        assertThat(response.execution()).isNull();
        assertThat(response.result()).isNull();
    }

    @Test
    void latestReturnsStaleRunWhenCurrentContextHasNoRunAndChecksAccess() {
        UUID projectId = UUID.randomUUID();
        UUID actorUserId = UUID.randomUUID();
        UUID currentSourceRevisionId = UUID.randomUUID();
        UUID staleSourceRevisionId = UUID.randomUUID();
        UUID staleRunId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        KbScanView stale = run(projectId, staleRunId, taskId, staleSourceRevisionId, TaskStatus.SUCCEEDED);
        when(projectContextService.snapshot(projectId)).thenReturn(new ProjectContextSnapshot(currentSourceRevisionId, 2L));
        when(kbScanRepository.findLatestRunBySourceRevision(projectId, currentSourceRevisionId)).thenReturn(Optional.empty());
        when(kbScanRepository.findLatestRun(projectId)).thenReturn(Optional.of(stale));
        when(taskRepository.findById(taskId)).thenReturn(Optional.of(task(projectId, taskId, TaskStatus.SUCCEEDED)));

        DomainLatestResponse<KbScanResponse> response = service().latest(projectId, actorUserId, false);

        assertThat(response.freshness()).isEqualTo(DomainLatestFreshness.STALE);
        assertThat(response.execution().status()).isEqualTo(TaskStatus.SUCCEEDED);
        assertThat(response.result().id()).isEqualTo(staleRunId);
        verify(projectAccessService).requireProjectAccess(projectId, actorUserId, false);
    }

    private KbScanService service() {
        return new KbScanService(
                kbScanRepository,
                sourceRepository,
                projectAccessService,
                taskService,
                taskRepository,
                projectContextService,
                auditLogService,
                new RvPortProperties(null, null, null),
                storedArtifactService,
                nodeReportInclusionService,
                kbAiExtensionRepository
        );
    }

    private KbScanView run(UUID projectId, UUID runId, UUID taskId, UUID sourceRevisionId, TaskStatus status) {
        return new KbScanView(
                runId,
                projectId,
                taskId,
                sourceRevisionId,
                "rules",
                Map.of(),
                status,
                Map.of("findingCount", 1),
                OffsetDateTime.now(),
                OffsetDateTime.now()
        );
    }

    private TaskView task(UUID projectId, UUID taskId, TaskStatus status) {
        return new TaskView(
                taskId,
                projectId,
                "KB_SCAN",
                status,
                0,
                "done",
                UUID.randomUUID(),
                OffsetDateTime.now(),
                null,
                null,
                OffsetDateTime.now(),
                60,
                status == TaskStatus.FAILED ? "KB_SCAN_FAILED" : null,
                status == TaskStatus.FAILED ? "failed" : null,
                0
        );
    }
}
