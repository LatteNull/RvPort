package cn.rvport.backend.report;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.artifact.StoredArtifactOwnerType;
import cn.rvport.backend.artifact.StoredArtifactRepository;
import cn.rvport.backend.artifact.StoredArtifactResource;
import cn.rvport.backend.artifact.StoredArtifactService;
import cn.rvport.backend.artifact.StoredArtifactView;
import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.migration.MigrationInputRefView;
import cn.rvport.backend.migration.MigrationInputService;
import cn.rvport.backend.migration.MigrationInputSourceType;
import cn.rvport.backend.migration.MigrationInputStatus;
import cn.rvport.backend.project.ProjectAccessService;
import cn.rvport.backend.reportcomparison.ReportComparisonRepository;
import cn.rvport.backend.source.SourceRepository;
import cn.rvport.backend.source.SourceRevisionType;
import cn.rvport.backend.source.SourceRevisionView;
import cn.rvport.backend.task.RvPortTaskTypes;
import cn.rvport.backend.task.TaskCreateCommand;
import cn.rvport.backend.task.TaskResponse;
import cn.rvport.backend.task.TaskRepository;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.task.TaskService;
import cn.rvport.backend.task.TaskView;
import cn.rvport.backend.workflow.DomainLatestFreshness;
import cn.rvport.backend.workflow.ProjectContextService;
import cn.rvport.backend.workflow.ProjectContextSnapshot;
import cn.rvport.backend.workflow.StageReadinessService;
import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.mock.web.MockHttpServletRequest;

@ExtendWith(MockitoExtension.class)
class ReportServiceTests {

    @Mock
    private ReportRepository reportRepository;

    @Mock
    private SourceRepository sourceRepository;

    @Mock
    private ProjectAccessService projectAccessService;

    @Mock
    private TaskService taskService;

    @Mock
    private StoredArtifactRepository storedArtifactRepository;

    @Mock
    private StoredArtifactService storedArtifactService;

    @Mock
    private ReportComparisonRepository reportComparisonRepository;

    @Mock
    private MigrationInputService migrationInputService;

    @Mock
    private TaskRepository taskRepository;

    @Mock
    private ProjectContextService projectContextService;

    @Mock
    private StageReadinessService stageReadinessService;

    @Test
    void createsReportTaskForActiveSourceRevision() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        when(sourceRepository.findActive(projectId)).thenReturn(Optional.of(sourceRevision(projectId, sourceRevisionId, "v1")));
        when(taskService.create(any())).thenReturn(task(taskId, projectId));
        when(reportRepository.createEvaluation(any(), eq(projectId), eq(sourceRevisionId), eq(taskId), eq("迁移评估报告 - v1"), eq(actorId)))
                .thenReturn(report(UUID.randomUUID(), projectId, sourceRevisionId, taskId));

        TaskResponse response = service().createEvaluation(projectId, new ReportGenerateRequest(null), actorId, false, new MockHttpServletRequest());

        assertThat(response.id()).isEqualTo(taskId);
        verify(projectAccessService).requireProjectAccess(projectId, actorId, false);
        ArgumentCaptor<TaskCreateCommand> commandCaptor = ArgumentCaptor.forClass(TaskCreateCommand.class);
        verify(taskService).create(commandCaptor.capture());
        assertThat(commandCaptor.getValue().type()).isEqualTo(RvPortTaskTypes.REPORT_GENERATE);
        assertThat(commandCaptor.getValue().inputSnapshot().get("projectId")).isEqualTo(projectId);
        assertThat(commandCaptor.getValue().inputSnapshot().get("sourceRevisionId")).isEqualTo(sourceRevisionId);
        assertThat(commandCaptor.getValue().inputSnapshot()).containsKey("reportId");
    }

    @Test
    void rejectsMissingActiveRevisionAndCrossProjectRevision() {
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        ReportService service = service();
        when(sourceRepository.findActive(projectId)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.createEvaluation(projectId, new ReportGenerateRequest(null), actorId, false, new MockHttpServletRequest()))
                .isInstanceOf(ApiException.class)
                .hasMessage("项目没有可用的 active source revision")
                .extracting("code")
                .isEqualTo("SOURCE_REVISION_ACTIVE_NOT_FOUND");

        UUID revisionId = UUID.randomUUID();
        when(sourceRepository.findById(revisionId)).thenReturn(Optional.of(sourceRevision(UUID.randomUUID(), revisionId, "foreign")));
        assertThatThrownBy(() -> service.createEvaluation(projectId, new ReportGenerateRequest(revisionId), actorId, false, new MockHttpServletRequest()))
                .isInstanceOf(ApiException.class)
                .hasMessage("源码版本不存在");
    }

    @Test
    void reportIdEntrypointsRequireProjectAccessAndDownloadThroughObjectStorage() {
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        UUID reportId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        UUID artifactId = UUID.randomUUID();
        ReportView report = report(reportId, projectId, UUID.randomUUID(), taskId);
        StoredArtifactView artifact = artifact(artifactId, projectId, taskId, reportId, ReportDownloadFormat.HTML.artifactType(), "text/html");
        when(reportRepository.findById(reportId)).thenReturn(Optional.of(report));
        when(storedArtifactRepository.findByOwner(StoredArtifactOwnerType.MIGRATION_REPORT, reportId, ReportDownloadFormat.HTML.artifactType()))
                .thenReturn(Optional.of(artifact));
        when(storedArtifactService.download(artifactId)).thenReturn(new StoredArtifactResource(artifact,
                new ByteArrayResource("<html>ok</html>".getBytes(StandardCharsets.UTF_8))));

        ReportService.DownloadableReport download = service().download(reportId, "HTML", actorId, false);

        assertThat(download.filename()).endsWith(".html");
        assertThat(download.contentType()).isEqualTo("text/html");
        verify(projectAccessService).requireProjectAccess(projectId, actorId, false);
    }

    @Test
    void rejectsInvalidQueriesAndMissingArtifactsSafely() {
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        UUID reportId = UUID.randomUUID();
        when(reportRepository.count(eq(projectId), any())).thenThrow(new IllegalArgumentException("bad sort"));
        when(reportRepository.findById(reportId)).thenReturn(Optional.of(report(reportId, projectId, UUID.randomUUID(), UUID.randomUUID())));

        assertThatThrownBy(() -> service().list(projectId, new ReportListRequest(1, 20, null, null, null, null, null, "serverPath", null), actorId, false))
                .isInstanceOf(ApiException.class)
                .hasMessage("报告查询参数不正确")
                .extracting("code")
                .isEqualTo("REPORT_QUERY_INVALID");

        assertThatThrownBy(() -> service().download(reportId, "XML", actorId, false))
                .isInstanceOf(ApiException.class)
                .hasMessage("报告下载格式不正确")
                .extracting("code")
                .isEqualTo("REPORT_FORMAT_INVALID");

        assertThatThrownBy(() -> service().download(reportId, "JSON", actorId, false))
                .isInstanceOf(ApiException.class)
                .hasMessage("报告制品不存在")
                .extracting("code")
                .isEqualTo("REPORT_ARTIFACT_NOT_FOUND");
    }

    @Test
    void readinessReturnsBlockerWhenProjectHasNoActiveSourceRevision() {
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        when(sourceRepository.findActive(projectId)).thenReturn(Optional.empty());
        when(reportRepository.latest(projectId, null)).thenReturn(Optional.empty());

        ReportReadinessResponse response = service().readiness(projectId, null, actorId, false);

        assertThat(response.canGenerate()).isFalse();
        assertThat(response.sourceRevision()).isNull();
        assertThat(response.inputSummary().total()).isZero();
        assertThat(response.blockers()).extracting(ReportReadinessIssueResponse::code)
                .containsExactly("SOURCE_REVISION_REQUIRED");
        verify(projectAccessService).requireProjectAccess(projectId, actorId, false);
    }

    @Test
    void readinessSummarizesInputsAndWarnsAboutLowCandidates() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        UUID latestReportId = UUID.randomUUID();
        SourceRevisionView revision = sourceRevision(projectId, sourceRevisionId, "v1");
        ReportView latestReport = report(latestReportId, projectId, sourceRevisionId, UUID.randomUUID());
        when(sourceRepository.findActive(projectId)).thenReturn(Optional.of(revision));
        when(migrationInputService.currentRefsForSystem(projectId, sourceRevisionId)).thenReturn(List.of(
                migrationInput(projectId, sourceRevisionId, MigrationInputSourceType.KB_FINDING, "HIGH", MigrationInputStatus.CONFIRMED),
                migrationInput(projectId, sourceRevisionId, MigrationInputSourceType.KB_FINDING, "HIGH", MigrationInputStatus.CONFIRMED),
                migrationInput(projectId, sourceRevisionId, MigrationInputSourceType.DEPENDENCY_RESULT, "LOW/TARGET_NEWER", MigrationInputStatus.CANDIDATE),
                migrationInput(projectId, sourceRevisionId, MigrationInputSourceType.DEPENDENCY_RESULT, "LOW/TARGET_NEWER", MigrationInputStatus.CANDIDATE),
                migrationInput(projectId, sourceRevisionId, MigrationInputSourceType.DEPENDENCY_RESULT, "LOW/TARGET_NEWER", MigrationInputStatus.CANDIDATE),
                migrationInput(projectId, sourceRevisionId, MigrationInputSourceType.KB_FINDING, "MEDIUM", MigrationInputStatus.EXCLUDED)
        ));
        when(reportRepository.latestSucceeded(projectId, sourceRevisionId)).thenReturn(Optional.of(latestReport));
        when(reportRepository.findById(latestReportId)).thenReturn(Optional.of(latestReport));
        when(migrationInputService.currentConfirmedRefsForSystem(projectId, sourceRevisionId)).thenReturn(List.of());
        when(reportRepository.listAllInputs(latestReportId)).thenReturn(List.of());
        when(storedArtifactRepository.listByOwner(StoredArtifactOwnerType.MIGRATION_REPORT, latestReportId)).thenReturn(List.of());
        when(reportComparisonRepository.latestComparableBase(latestReport)).thenReturn(Optional.empty());
        when(reportComparisonRepository.latestForTargetReport(latestReportId)).thenReturn(Optional.empty());

        ReportReadinessResponse response = service().readiness(projectId, null, actorId, false);

        assertThat(response.canGenerate()).isTrue();
        assertThat(response.blockers()).isEmpty();
        assertThat(response.sourceRevision().id()).isEqualTo(sourceRevisionId);
        assertThat(response.inputSummary().confirmed()).isEqualTo(2);
        assertThat(response.inputSummary().candidate()).isEqualTo(3);
        assertThat(response.inputSummary().excluded()).isEqualTo(1);
        assertThat(response.inputSummary().lowCandidate()).isEqualTo(3);
        assertThat(response.inputSummary().bySourceType()).containsEntry("KB_FINDING", 3L);
        assertThat(response.warnings()).extracting(ReportReadinessIssueResponse::code)
                .contains("LOW_CANDIDATES_NOT_INCLUDED", "EXCLUDED_INPUTS_PRESENT");
        assertThat(response.latestReport().id()).isEqualTo(latestReportId);
    }

    @Test
    void readinessAllowsPerfectReportWithoutConfirmedInputs() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        when(sourceRepository.findActive(projectId)).thenReturn(Optional.of(sourceRevision(projectId, sourceRevisionId, "v1")));
        when(migrationInputService.currentRefsForSystem(projectId, sourceRevisionId)).thenReturn(List.of(
                migrationInput(projectId, sourceRevisionId, MigrationInputSourceType.DEPENDENCY_RESULT, "LOW", MigrationInputStatus.CANDIDATE)
        ));

        ReportReadinessResponse response = service().readiness(projectId, null, actorId, false);

        assertThat(response.canGenerate()).isTrue();
        assertThat(response.blockers()).isEmpty();
        assertThat(response.warnings()).extracting(ReportReadinessIssueResponse::code)
                .contains("LOW_CANDIDATES_NOT_INCLUDED");
    }

    @Test
    void reportDetailIncludesCurrentInputSummary() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        UUID reportId = UUID.randomUUID();
        ReportView report = report(reportId, projectId, sourceRevisionId, UUID.randomUUID());
        when(reportRepository.findById(reportId)).thenReturn(Optional.of(report));
        when(storedArtifactRepository.listByOwner(StoredArtifactOwnerType.MIGRATION_REPORT, reportId)).thenReturn(List.of());
        when(reportComparisonRepository.latestComparableBase(report)).thenReturn(Optional.empty());
        when(reportComparisonRepository.latestForTargetReport(reportId)).thenReturn(Optional.empty());
        when(migrationInputService.currentRefsForSystem(projectId, sourceRevisionId)).thenReturn(List.of(
                migrationInput(projectId, sourceRevisionId, MigrationInputSourceType.KB_FINDING, "CRITICAL", MigrationInputStatus.CONFIRMED),
                migrationInput(projectId, sourceRevisionId, MigrationInputSourceType.DEPENDENCY_RESULT, "HIGH/MISSING", MigrationInputStatus.EXCLUDED),
                migrationInput(projectId, sourceRevisionId, MigrationInputSourceType.DEPENDENCY_RESULT, "HIGH/MISSING", MigrationInputStatus.EXCLUDED)
        ));
        when(migrationInputService.currentConfirmedRefsForSystem(projectId, sourceRevisionId)).thenReturn(List.of(
                migrationInput(projectId, sourceRevisionId, MigrationInputSourceType.KB_FINDING, "CRITICAL", MigrationInputStatus.CONFIRMED)
        ));

        ReportResponse response = service().get(reportId, actorId, false);

        assertThat(response.summary()).containsEntry("confirmedInputCount", 1);
        assertThat(response.currentInputSummary().total()).isEqualTo(3);
        assertThat(response.currentInputSummary().confirmed()).isEqualTo(1);
        assertThat(response.currentInputSummary().excluded()).isEqualTo(2);
        verify(projectAccessService).requireProjectAccess(projectId, actorId, false);
    }

    @Test
    void reportDetailExposesOnlyDownloadableReportArtifacts() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        UUID reportId = UUID.randomUUID();
        ReportView report = report(reportId, projectId, sourceRevisionId, UUID.randomUUID());
        StoredArtifactView html = artifact(UUID.randomUUID(), projectId, report.taskId(), reportId,
                "MIGRATION_REPORT_HTML", "text/html");
        StoredArtifactView json = artifact(UUID.randomUUID(), projectId, report.taskId(), reportId,
                "MIGRATION_REPORT_JSON", "application/json");
        StoredArtifactView sourceContext = artifact(UUID.randomUUID(), projectId, report.taskId(), reportId,
                "SOURCE_CONTEXT_file-key", "text/plain");
        when(reportRepository.findById(reportId)).thenReturn(Optional.of(report));
        when(storedArtifactRepository.listByOwner(StoredArtifactOwnerType.MIGRATION_REPORT, reportId))
                .thenReturn(List.of(html, sourceContext, json));
        when(reportComparisonRepository.latestComparableBase(report)).thenReturn(Optional.empty());
        when(reportComparisonRepository.latestForTargetReport(reportId)).thenReturn(Optional.empty());
        when(migrationInputService.currentRefsForSystem(projectId, sourceRevisionId)).thenReturn(List.of());
        when(migrationInputService.currentConfirmedRefsForSystem(projectId, sourceRevisionId)).thenReturn(List.of());

        ReportResponse response = service().get(reportId, actorId, false);

        assertThat(response.artifacts()).extracting(ReportArtifactSummaryResponse::artifactType)
                .containsExactly("MIGRATION_REPORT_HTML", "MIGRATION_REPORT_JSON");
    }

    @Test
    void inputPreviewPaginatesAndRejectsInvalidQueries() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        ReportInputPreviewListRequest query = new ReportInputPreviewListRequest(
                1, 10, sourceRevisionId, MigrationInputSourceType.KB_FINDING, MigrationInputStatus.CONFIRMED,
                "HIGH", "AVX", "updatedAt", "desc");
        when(sourceRepository.findById(sourceRevisionId)).thenReturn(Optional.of(sourceRevision(projectId, sourceRevisionId, "v1")));
        when(migrationInputService.currentRefsForSystem(projectId, sourceRevisionId)).thenReturn(List.of(
                migrationInput(projectId, sourceRevisionId, MigrationInputSourceType.KB_FINDING, "HIGH", MigrationInputStatus.CONFIRMED)
        ));

        PageResponse<ReportInputPreviewResponse> page = service().inputPreview(projectId, query, actorId, false);

        assertThat(page.total()).isEqualTo(1);
        assertThat(page.items()).hasSize(1);
        assertThat(page.items().getFirst().sourceLocation()).containsEntry("sourceType", "KB_FINDING");

        ReportInputPreviewListRequest invalid = new ReportInputPreviewListRequest(1, 10, sourceRevisionId, null, null,
                "HIGH", null, "serverPath", "desc");
        assertThatThrownBy(() -> service().inputPreview(projectId, invalid, actorId, false))
                .isInstanceOf(ApiException.class)
                .extracting("code")
                .isEqualTo("REPORT_INPUT_PREVIEW_QUERY_INVALID");
    }

    @Test
    void latestDistinguishesCurrentStaleAndEmptyResults() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        ReportView current = report(UUID.randomUUID(), projectId, revisionId, taskId);
        when(projectContextService.snapshot(projectId)).thenReturn(new ProjectContextSnapshot(revisionId, 3L));
        when(reportRepository.latestEvaluation(projectId, revisionId)).thenReturn(Optional.of(current));
        when(taskRepository.findById(taskId)).thenReturn(Optional.of(taskView(taskId, projectId)));

        var currentResponse = fullService().latest(projectId, null, actorId, false);

        assertThat(currentResponse.freshness()).isEqualTo(DomainLatestFreshness.CURRENT);
        assertThat(currentResponse.execution().taskId()).isEqualTo(taskId);

        UUID requestedRevision = UUID.randomUUID();
        when(reportRepository.latestEvaluation(projectId, requestedRevision)).thenReturn(Optional.empty());
        when(reportRepository.latestEvaluation(projectId, null)).thenReturn(Optional.of(current));
        assertThat(fullService().latest(projectId, requestedRevision, actorId, false).freshness())
                .isEqualTo(DomainLatestFreshness.STALE);

        when(reportRepository.latestEvaluation(projectId, null)).thenReturn(Optional.empty());
        var empty = fullService().latest(projectId, requestedRevision, actorId, false);
        assertThat(empty.freshness()).isEqualTo(DomainLatestFreshness.EMPTY);
        assertThat(empty.execution()).isNull();
        assertThat(empty.result()).isNull();
    }

    @Test
    void reportDiffClassifiesAddedRemovedChangedAndUnchangedInputs() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        ReportView report = report(UUID.randomUUID(), projectId, revisionId, UUID.randomUUID());
        MigrationInputRefView added = migrationInput(projectId, revisionId, MigrationInputSourceType.KB_FINDING,
                "HIGH", MigrationInputStatus.CONFIRMED);
        MigrationInputRefView changed = migrationInput(projectId, revisionId, MigrationInputSourceType.KB_FINDING,
                "MEDIUM", MigrationInputStatus.CONFIRMED);
        MigrationInputRefView unchanged = migrationInput(projectId, revisionId, MigrationInputSourceType.DEPENDENCY_RESULT,
                "LOW/TARGET_NEWER", MigrationInputStatus.CONFIRMED);
        UUID removedId = UUID.randomUUID();
        when(reportRepository.findById(report.id())).thenReturn(Optional.of(report));
        when(migrationInputService.currentConfirmedRefsForSystem(projectId, revisionId))
                .thenReturn(List.of(added, changed, unchanged));
        when(migrationInputService.currentRefsForSystem(projectId, revisionId))
                .thenReturn(List.of(added, changed, unchanged));
        when(reportRepository.listAllInputs(report.id())).thenReturn(List.of(
                reportInput(report.id(), changed.id(), null),
                reportInput(report.id(), unchanged.id(), snapshot(unchanged)),
                reportInput(report.id(), removedId, Map.of(
                        "issueTitle", "removed", "sourceType", "KB_FINDING",
                        "detectedLevel", "HIGH", "locationLabel", "src/old.c:2"))));

        ReportResponse response = service().get(report.id(), actorId, false);

        assertThat(response.reportUpToDate()).isFalse();
        assertThat(response.reportDiffSummary().added()).isEqualTo(1);
        assertThat(response.reportDiffSummary().changed()).isEqualTo(1);
        assertThat(response.reportDiffSummary().removed()).isEqualTo(1);
        assertThat(response.reportDiffSummary().addedSamples()).extracting(ReportUpdateSummaryResponse.Item::migrationInputRefId)
                .containsExactly(added.id());
        assertThat(response.reportDiffSummary().removedSamples()).extracting(ReportUpdateSummaryResponse.Item::migrationInputRefId)
                .containsExactly(removedId);
    }

    @Test
    void inputPreviewSupportsEverySortFieldAndNullableKeywordFields() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        when(sourceRepository.findById(revisionId)).thenReturn(Optional.of(sourceRevision(projectId, revisionId, "v1")));
        MigrationInputRefView ref = new MigrationInputRefView(UUID.randomUUID(), UUID.randomUUID(), projectId, revisionId,
                null, MigrationInputSourceType.KB_FINDING, UUID.randomUUID(), null, null, null,
                null, null, null, null, null, MigrationInputStatus.CANDIDATE, null, null, null);
        when(migrationInputService.currentRefsForSystem(projectId, revisionId)).thenReturn(List.of(ref));

        for (String sort : List.of("createdAt", "updatedAt", "sourceType", "detectedLevel", "status", "issueTitle", "locationLabel")) {
            PageResponse<ReportInputPreviewResponse> page = service().inputPreview(projectId,
                    new ReportInputPreviewListRequest(null, null, revisionId, null, null, null, "missing", sort, "asc"),
                    actorId, false);
            assertThat(page.items()).isEmpty();
        }
        assertThatThrownBy(() -> service().inputPreview(projectId,
                new ReportInputPreviewListRequest(1, 20, revisionId, null, null, "UNKNOWN", null, null, null),
                actorId, false)).isInstanceOf(ApiException.class)
                .extracting("code").isEqualTo("REPORT_INPUT_PREVIEW_QUERY_INVALID");
    }

    @Test
    void readinessRejectsMissingAndForeignExplicitRevision() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        when(sourceRepository.findById(revisionId)).thenReturn(Optional.empty());
        assertThatThrownBy(() -> service().readiness(projectId, revisionId, actorId, false))
                .isInstanceOf(ApiException.class).extracting("code").isEqualTo("SOURCE_REVISION_NOT_FOUND");

        when(sourceRepository.findById(revisionId))
                .thenReturn(Optional.of(sourceRevision(UUID.randomUUID(), revisionId, "foreign")));
        assertThatThrownBy(() -> service().readiness(projectId, revisionId, actorId, false))
                .isInstanceOf(ApiException.class).extracting("code").isEqualTo("SOURCE_REVISION_NOT_FOUND");
    }

    @Test
    void reportDiffDetectsEachVisibleFieldChangeAndHandlesNullCollections() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        ReportView report = report(UUID.randomUUID(), projectId, revisionId, UUID.randomUUID());
        List<MigrationInputRefView> refs = new ArrayList<>();
        List<ReportInputView> inputs = new ArrayList<>();
        for (String field : List.of("issueTitle", "detectedLevel", "locationLabel", "recommendationSummary", "status", "note")) {
            MigrationInputRefView ref = migrationInput(projectId, revisionId, MigrationInputSourceType.KB_FINDING,
                    "HIGH", MigrationInputStatus.CONFIRMED);
            Map<String, Object> changedSnapshot = new HashMap<>(snapshot(ref));
            changedSnapshot.put(field, "different");
            refs.add(ref);
            inputs.add(reportInput(report.id(), ref.id(), changedSnapshot));
        }
        UUID removedId = UUID.randomUUID();
        inputs.add(reportInput(report.id(), removedId, null));
        when(reportRepository.findById(report.id())).thenReturn(Optional.of(report));
        when(migrationInputService.currentRefsForSystem(projectId, revisionId)).thenReturn(refs);
        when(migrationInputService.currentConfirmedRefsForSystem(projectId, revisionId)).thenReturn(refs);
        when(reportRepository.listAllInputs(report.id())).thenReturn(inputs);

        ReportUpdateSummaryResponse diff = service().get(report.id(), actorId, false).reportDiffSummary();

        assertThat(diff.changed()).isEqualTo(6);
        assertThat(diff.changedSamples()).hasSize(5);
        assertThat(diff.removed()).isEqualTo(1);
        assertThat(diff.removedSamples().getFirst().issueTitle()).isNull();

        ReportView nullCollectionsReport = report(UUID.randomUUID(), projectId, revisionId, UUID.randomUUID());
        when(reportRepository.findById(nullCollectionsReport.id())).thenReturn(Optional.of(nullCollectionsReport));
        when(migrationInputService.currentRefsForSystem(projectId, revisionId)).thenReturn(List.of());
        when(migrationInputService.currentConfirmedRefsForSystem(projectId, revisionId)).thenReturn(null);
        when(reportRepository.listAllInputs(nullCollectionsReport.id())).thenReturn(null);
        assertThat(service().get(nullCollectionsReport.id(), actorId, false).reportDiffSummary().upToDate()).isTrue();
    }

    @Test
    void inputPreviewMatchesEveryTextFieldAndFilterCombination() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        when(sourceRepository.findById(revisionId)).thenReturn(Optional.of(sourceRevision(projectId, revisionId, "v1")));
        MigrationInputRefView ref = new MigrationInputRefView(UUID.randomUUID(), UUID.randomUUID(), projectId, revisionId,
                "Issue Needle", MigrationInputSourceType.KB_FINDING, UUID.randomUUID(), "HIGH", "src/location.c:8",
                "Recommendation Token", "rule", "src/location.c", "symbol", "anchor", "fingerprint",
                MigrationInputStatus.CONFIRMED, "Note Marker", OffsetDateTime.now(), OffsetDateTime.now());
        when(migrationInputService.currentRefsForSystem(projectId, revisionId)).thenReturn(List.of(ref));

        for (String keyword : List.of("needle", "LOCATION", "token", "marker")) {
            assertThat(service().inputPreview(projectId,
                    new ReportInputPreviewListRequest(1, 20, revisionId, MigrationInputSourceType.KB_FINDING,
                            MigrationInputStatus.CONFIRMED, "high", keyword, "createdAt", "asc"), actorId, false)
                    .items()).hasSize(1);
        }
        assertThat(service().inputPreview(projectId,
                new ReportInputPreviewListRequest(1, 20, revisionId, MigrationInputSourceType.DEPENDENCY_RESULT,
                        null, null, null, null, null), actorId, false).items()).isEmpty();
        assertThat(service().inputPreview(projectId,
                new ReportInputPreviewListRequest(1, 20, revisionId, null,
                        MigrationInputStatus.EXCLUDED, null, " ", null, "desc"), actorId, false).items()).isEmpty();
        assertThat(service().inputPreview(projectId,
                new ReportInputPreviewListRequest(1, 20, revisionId, null, null,
                        "LOW", null, "", null), actorId, false).items()).isEmpty();
    }

    @Test
    void createEvaluationAcceptsNullRequestAndUsesRevisionIdAsBlankLabelFallback() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        SourceRevisionView revision = sourceRevision(projectId, revisionId, " ");
        when(sourceRepository.findActive(projectId)).thenReturn(Optional.of(revision));
        when(taskService.create(any())).thenReturn(task(UUID.randomUUID(), projectId));

        fullService().createEvaluation(projectId, null, actorId, false, new MockHttpServletRequest());

        verify(stageReadinessService).requireSatisfied(eq(projectId), any(), any(), eq(actorId), eq(false));
        verify(reportRepository).createEvaluation(any(), eq(projectId), eq(revisionId), any(),
                eq("迁移评估报告 - " + revisionId), eq(actorId));
    }

    private ReportService service() {
        return new ReportService(reportRepository, sourceRepository, projectAccessService, taskService,
                storedArtifactRepository, storedArtifactService, reportComparisonRepository, migrationInputService);
    }

    private ReportService fullService() {
        return new ReportService(reportRepository, sourceRepository, projectAccessService, taskService,
                taskRepository, projectContextService, stageReadinessService, storedArtifactRepository,
                storedArtifactService, reportComparisonRepository, migrationInputService);
    }

    private ReportInputView reportInput(UUID reportId, UUID inputId, Map<String, Object> snapshot) {
        return new ReportInputView(UUID.randomUUID(), reportId, ReportInputType.MIGRATION_INPUT_REF,
                inputId, snapshot, OffsetDateTime.now());
    }

    private Map<String, Object> snapshot(MigrationInputRefView ref) {
        return Map.of(
                "issueTitle", ref.issueTitle(),
                "sourceType", ref.sourceType().name(),
                "detectedLevel", ref.detectedLevel(),
                "locationLabel", ref.locationLabel(),
                "recommendationSummary", ref.recommendationSummary(),
                "status", ref.status().name(),
                "note", ref.note());
    }

    private TaskView taskView(UUID taskId, UUID projectId) {
        return new TaskView(taskId, projectId, RvPortTaskTypes.REPORT_GENERATE, TaskStatus.SUCCEEDED, 100,
                "done", UUID.randomUUID(), OffsetDateTime.now(), null, OffsetDateTime.now(), OffsetDateTime.now(),
                60, null, null, 0);
    }

    private SourceRevisionView sourceRevision(UUID projectId, UUID sourceRevisionId, String label) {
        return new SourceRevisionView(sourceRevisionId, projectId, SourceRevisionType.GIT, label,
                "https://example.test/repo.git", "https://example.test/repo.git", "main", "abcdef", null,
                "/runtime/source", null, true, UUID.randomUUID(), OffsetDateTime.now());
    }

    private TaskResponse task(UUID taskId, UUID projectId) {
        return new TaskResponse(taskId, projectId, RvPortTaskTypes.REPORT_GENERATE, TaskStatus.PENDING, 0,
                "迁移评估报告任务已创建", OffsetDateTime.now(), null, null, null, null, null, Map.of());
    }

    private ReportView report(UUID reportId, UUID projectId, UUID sourceRevisionId, UUID taskId) {
        return new ReportView(reportId, projectId, taskId, sourceRevisionId, ReportType.EVALUATION, TaskStatus.SUCCEEDED,
                "迁移评估报告", Map.of("confirmedInputCount", 1), "HIGH", UUID.randomUUID(), OffsetDateTime.now(), OffsetDateTime.now());
    }

    private StoredArtifactView artifact(UUID artifactId, UUID projectId, UUID taskId, UUID reportId, String artifactType, String contentType) {
        return new StoredArtifactView(artifactId, projectId, taskId, StoredArtifactOwnerType.MIGRATION_REPORT, reportId,
                artifactType, "rvport-artifacts", "projects/test/report.html", contentType, 10, "0".repeat(64), Map.of(), OffsetDateTime.now());
    }

    private MigrationInputRefView migrationInput(UUID projectId, UUID sourceRevisionId, MigrationInputSourceType sourceType,
                                                 String detectedLevel, MigrationInputStatus status) {
        return new MigrationInputRefView(
                UUID.randomUUID(),
                UUID.randomUUID(),
                projectId,
                sourceRevisionId,
                "AVX intrinsic",
                sourceType,
                UUID.randomUUID(),
                detectedLevel,
                "src/main.c:1",
                "replace x86 intrinsic",
                "rule",
                "src/main.c",
                "main",
                "anchor",
                "fingerprint",
                status,
                "note",
                OffsetDateTime.now(),
                OffsetDateTime.now()
        );
    }
}
