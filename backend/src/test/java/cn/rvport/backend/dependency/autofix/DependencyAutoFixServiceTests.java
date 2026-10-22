package cn.rvport.backend.dependency.autofix;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.audit.AuditLogService;
import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.dependency.DependencyAnalysisRepository;
import cn.rvport.backend.dependency.DependencyAnalysisResultItemView;
import cn.rvport.backend.dependency.DependencyAnalysisView;
import cn.rvport.backend.dependency.DependencyConfidence;
import cn.rvport.backend.dependency.DependencyRiskLevel;
import cn.rvport.backend.dependency.DependencyTargetMatchStatus;
import cn.rvport.backend.dependency.DependencyType;
import cn.rvport.backend.project.ProjectAccessService;
import cn.rvport.backend.project.runtime.ProjectRuntimeEnvironmentResponse;
import cn.rvport.backend.project.runtime.ProjectRuntimeEnvironmentService;
import cn.rvport.backend.source.SourceRepository;
import cn.rvport.backend.source.SourceRevisionType;
import cn.rvport.backend.source.SourceRevisionView;
import cn.rvport.backend.source.deploy.SourceDeployEnvironmentSummary;
import cn.rvport.backend.task.RvPortTaskTypes;
import cn.rvport.backend.task.TaskCreateCommand;
import cn.rvport.backend.task.TaskResponse;
import cn.rvport.backend.task.TaskService;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.task.TaskView;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class DependencyAutoFixServiceTests {

    @Mock
    private DependencyAutoFixRepository repository;
    @Mock
    private DependencyAnalysisRepository dependencyAnalysisRepository;
    @Mock
    private ProjectRuntimeEnvironmentService runtimeEnvironmentService;
    @Mock
    private SourceRepository sourceRepository;
    @Mock
    private ProjectAccessService projectAccessService;
    @Mock
    private TaskService taskService;
    @Mock
    private AuditLogService auditLogService;

    @Test
    void returnsPagedAndFilteredCandidates() {
        Fixtures fixtures = fixtures();
        when(dependencyAnalysisRepository.findById(fixtures.analysis.id())).thenReturn(Optional.of(fixtures.analysis));
        when(dependencyAnalysisRepository.listResultItemViews(fixtures.analysis.id())).thenReturn(List.of(
                result(fixtures, DependencyRiskLevel.MEDIUM, "zlib", "1.2.13"),
                result(fixtures, DependencyRiskLevel.HIGH, "gcc", null),
                result(fixtures, DependencyRiskLevel.LOW, "glibc", null)
        ));

        PageResponse<DependencyAutoFixCandidateResponse> page = service().candidates(
                fixtures.analysis.id(),
                new DependencyAutoFixCandidateListRequest(1, 1, null, null, null, true, null, null,
                        "installPackageName", "asc"),
                fixtures.userId,
                false
        );

        assertThat(page.total()).isEqualTo(1);
        assertThat(page.items()).extracting(DependencyAutoFixCandidateResponse::installPackageName)
                .containsExactly("zlib");
        verify(projectAccessService).requireProjectAccess(fixtures.projectId, fixtures.userId, false);
    }

    @Test
    void rejectsInvalidCandidateSort() {
        Fixtures fixtures = fixtures();
        when(dependencyAnalysisRepository.findById(fixtures.analysis.id())).thenReturn(Optional.of(fixtures.analysis));

        assertThatThrownBy(() -> service().candidates(
                fixtures.analysis.id(),
                new DependencyAutoFixCandidateListRequest(1, 20, null, null, null, null, null, null,
                        "badField", "asc"),
                fixtures.userId,
                false
        ))
                .isInstanceOf(ApiException.class)
                .extracting("code")
                .isEqualTo("DEPENDENCY_AUTO_FIX_QUERY_INVALID");
    }

    @Test
    void rejectsStaleAnalysisContext() {
        Fixtures fixtures = fixtures();
        when(dependencyAnalysisRepository.findById(fixtures.analysis.id())).thenReturn(Optional.of(fixtures.analysis));
        when(sourceRepository.findActive(fixtures.projectId)).thenReturn(Optional.of(sourceRevision(UUID.randomUUID(), fixtures.projectId)));
        when(runtimeEnvironmentService.currentVersion(fixtures.projectId)).thenReturn(fixtures.analysis.environmentConfigVersion());

        assertThatThrownBy(() -> service().create(
                fixtures.analysis.id(),
                new DependencyAutoFixCreateRequest(List.of(UUID.randomUUID()), true),
                fixtures.userId,
                false,
                null
        ))
                .isInstanceOf(ApiException.class)
                .extracting("code")
                .isEqualTo("DEPENDENCY_AUTO_FIX_ANALYSIS_STALE");
    }

    @Test
    void rejectsDuplicateResultItems() {
        Fixtures fixtures = currentFixtures();
        UUID itemId = UUID.randomUUID();

        assertThatThrownBy(() -> service().create(
                fixtures.analysis.id(),
                new DependencyAutoFixCreateRequest(List.of(itemId, itemId), true),
                fixtures.userId,
                false,
                null
        ))
                .isInstanceOf(ApiException.class)
                .extracting("code")
                .isEqualTo("DEPENDENCY_AUTO_FIX_ITEM_DUPLICATED");
    }

    @Test
    void rejectsUnselectableResultItem() {
        Fixtures fixtures = currentFixtures();
        DependencyAnalysisResultItemView item = result(fixtures, DependencyRiskLevel.LOW, "glibc", null);
        when(dependencyAnalysisRepository.listResultItemViews(fixtures.analysis.id())).thenReturn(List.of(item));

        assertThatThrownBy(() -> service().create(
                fixtures.analysis.id(),
                new DependencyAutoFixCreateRequest(List.of(item.id()), true),
                fixtures.userId,
                false,
                null
        ))
                .isInstanceOf(ApiException.class)
                .extracting("code")
                .isEqualTo("DEPENDENCY_AUTO_FIX_ITEM_INVALID");
    }

    @Test
    void createsTaskAndStoresSelectedCandidate() {
        Fixtures fixtures = currentFixtures();
        DependencyAnalysisResultItemView item = result(fixtures, DependencyRiskLevel.MEDIUM, "zlib", "1.2.13");
        UUID taskId = UUID.randomUUID();
        when(dependencyAnalysisRepository.listResultItemViews(fixtures.analysis.id())).thenReturn(List.of(item));
        when(taskService.create(any())).thenReturn(TaskResponse.from(task(taskId, fixtures.projectId, fixtures.userId)));

        DependencyAutoFixCreateResponse response = service().create(
                fixtures.analysis.id(),
                new DependencyAutoFixCreateRequest(List.of(item.id()), true),
                fixtures.userId,
                false,
                null
        );

        assertThat(response.selectedCount()).isEqualTo(1);
        assertThat(response.taskId()).isEqualTo(taskId);
        ArgumentCaptor<TaskCreateCommand> taskCaptor = ArgumentCaptor.forClass(TaskCreateCommand.class);
        verify(taskService).create(taskCaptor.capture());
        assertThat(taskCaptor.getValue().type()).isEqualTo(RvPortTaskTypes.DEPENDENCY_AUTO_FIX);
        verify(repository).createRun(eq(response.autoFixRunId()), eq(fixtures.projectId), eq(taskId),
                eq(fixtures.analysis.id()), eq(fixtures.sourceRevisionId), eq(fixtures.targetEnvironmentId),
                eq(fixtures.analysis.environmentConfigVersion()), eq(1));
        verify(repository).createItems(eq(response.autoFixRunId()), any(), eq(fixtures.projectId), eq(fixtures.sourceRevisionId));
    }

    @Test
    void listsCurrentRunsByInjectingActiveSourceAndEnvironmentVersion() {
        Fixtures fixtures = fixtures();
        DependencyAutoFixRunView run = autoFixRun(fixtures);
        DependencyAutoFixRunListRequest request = new DependencyAutoFixRunListRequest(
                null, null, null, null, null, null, "createdAt", "DESC");
        when(sourceRepository.findActive(fixtures.projectId))
                .thenReturn(Optional.of(sourceRevision(fixtures.sourceRevisionId, fixtures.projectId)));
        when(runtimeEnvironmentService.currentVersion(fixtures.projectId)).thenReturn(7L);
        when(repository.countRuns(eq(fixtures.projectId), any())).thenReturn(1L);
        when(repository.listRuns(eq(fixtures.projectId), any())).thenReturn(List.of(run));

        PageResponse<DependencyAutoFixRunResponse> page = service().list(
                fixtures.projectId, request, fixtures.userId, false);

        assertThat(page.total()).isEqualTo(1);
        assertThat(page.page()).isEqualTo(1);
        assertThat(page.pageSize()).isEqualTo(20);
        assertThat(page.items()).extracting(DependencyAutoFixRunResponse::id).containsExactly(run.id());
        ArgumentCaptor<DependencyAutoFixRunListRequest> requestCaptor =
                ArgumentCaptor.forClass(DependencyAutoFixRunListRequest.class);
        verify(repository).countRuns(eq(fixtures.projectId), requestCaptor.capture());
        assertThat(requestCaptor.getValue().sourceRevisionId()).isEqualTo(fixtures.sourceRevisionId);
        assertThat(requestCaptor.getValue().environmentConfigVersion()).isEqualTo(7L);
    }

    @Test
    void preservesExplicitOrIncludeStaleRunFiltersAndAcceptsBlankSorts() {
        Fixtures fixtures = fixtures();
        UUID explicitSource = UUID.randomUUID();
        for (DependencyAutoFixRunListRequest request : List.of(
                new DependencyAutoFixRunListRequest(2, 10, null, null, true, null, null, null),
                new DependencyAutoFixRunListRequest(2, 10, explicitSource, null, false, null, " ", " "),
                new DependencyAutoFixRunListRequest(2, 10, null, 9L, false, null, "status", "asc")
        )) {
            when(repository.countRuns(fixtures.projectId, request)).thenReturn(0L);

            PageResponse<DependencyAutoFixRunResponse> page = service().list(
                    fixtures.projectId, request, fixtures.userId, true);

            assertThat(page.page()).isEqualTo(2);
            assertThat(page.items()).isEmpty();
            verify(repository).countRuns(fixtures.projectId, request);
        }
    }

    @Test
    void rejectsInvalidRunAndItemSortFieldsAndDirections() {
        Fixtures fixtures = fixtures();
        DependencyAutoFixRunView run = autoFixRun(fixtures);
        when(repository.findRun(run.id())).thenReturn(Optional.of(run));

        assertThatThrownBy(() -> service().list(fixtures.projectId,
                new DependencyAutoFixRunListRequest(1, 20, null, null, null, null, "unknown", "asc"),
                fixtures.userId, false)).isInstanceOf(ApiException.class)
                .extracting("code").isEqualTo("DEPENDENCY_AUTO_FIX_QUERY_INVALID");
        assertThatThrownBy(() -> service().list(fixtures.projectId,
                new DependencyAutoFixRunListRequest(1, 20, null, null, null, null, "status", "sideways"),
                fixtures.userId, false)).isInstanceOf(ApiException.class);
        assertThatThrownBy(() -> service().items(run.id(),
                new DependencyAutoFixItemListRequest(1, 20, null, null, null, null, null, "unknown", "asc"),
                fixtures.userId, false)).isInstanceOf(ApiException.class);
        assertThatThrownBy(() -> service().items(run.id(),
                new DependencyAutoFixItemListRequest(1, 20, null, null, null, null, null,
                        "installPackageName", "up"), fixtures.userId, false)).isInstanceOf(ApiException.class);
    }

    @Test
    void getsRunAndListsItsItemsWithDefaults() {
        Fixtures fixtures = fixtures();
        DependencyAutoFixRunView run = autoFixRun(fixtures);
        DependencyAutoFixItemView item = autoFixItem(fixtures, run.id());
        DependencyAutoFixItemListRequest request = new DependencyAutoFixItemListRequest(
                null, null, null, null, null, null, null, "createdAt", "desc");
        when(repository.findRun(run.id())).thenReturn(Optional.of(run));
        when(repository.countItems(run.id(), request)).thenReturn(1L);
        when(repository.listItems(run.id(), request)).thenReturn(List.of(item));

        assertThat(service().get(run.id(), fixtures.userId, false).id()).isEqualTo(run.id());
        PageResponse<DependencyAutoFixItemResponse> page = service().items(
                run.id(), request, fixtures.userId, false);

        assertThat(page.page()).isEqualTo(1);
        assertThat(page.pageSize()).isEqualTo(20);
        assertThat(page.items()).extracting(DependencyAutoFixItemResponse::id).containsExactly(item.id());
        verify(projectAccessService, org.mockito.Mockito.times(2))
                .requireProjectAccess(fixtures.projectId, fixtures.userId, false);
    }

    @Test
    void reportsMissingAnalysisRunAndRejectsMissingOrEmptySelections() {
        Fixtures fixtures = fixtures();
        UUID missing = UUID.randomUUID();
        when(dependencyAnalysisRepository.findById(missing)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service().candidates(missing,
                new DependencyAutoFixCandidateListRequest(null, null, null, null, null, null,
                        null, null, null, null), fixtures.userId, false))
                .isInstanceOf(ApiException.class).extracting("code")
                .isEqualTo("DEPENDENCY_ANALYSIS_NOT_FOUND");
        for (DependencyAutoFixCreateRequest request : java.util.Arrays.asList(
                null, new DependencyAutoFixCreateRequest(null, true),
                new DependencyAutoFixCreateRequest(List.of(), true))) {
            assertThatThrownBy(() -> service().create(
                    fixtures.analysis.id(), request, fixtures.userId, false, null))
                    .isInstanceOf(ApiException.class).extracting("code")
                    .isEqualTo("DEPENDENCY_AUTO_FIX_ITEMS_REQUIRED");
        }
    }

    private DependencyAutoFixService service() {
        return new DependencyAutoFixService(repository, dependencyAnalysisRepository, runtimeEnvironmentService,
                sourceRepository, projectAccessService, taskService, auditLogService);
    }

    private Fixtures currentFixtures() {
        Fixtures fixtures = fixtures();
        when(dependencyAnalysisRepository.findById(fixtures.analysis.id())).thenReturn(Optional.of(fixtures.analysis));
        when(sourceRepository.findActive(fixtures.projectId)).thenReturn(Optional.of(sourceRevision(fixtures.sourceRevisionId, fixtures.projectId)));
        when(runtimeEnvironmentService.currentVersion(fixtures.projectId)).thenReturn(fixtures.analysis.environmentConfigVersion());
        when(runtimeEnvironmentService.summary(fixtures.projectId)).thenReturn(runtimeSummary(fixtures));
        return fixtures;
    }

    private Fixtures fixtures() {
        UUID projectId = UUID.randomUUID();
        UUID userId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID targetEnvironmentId = UUID.randomUUID();
        DependencyAnalysisView analysis = new DependencyAnalysisView(UUID.randomUUID(), projectId, UUID.randomUUID(),
                sourceRevisionId, UUID.randomUUID(), targetEnvironmentId, 7L, TaskStatus.SUCCEEDED,
                Map.of(), null, OffsetDateTime.now(), OffsetDateTime.now(), OffsetDateTime.now());
        return new Fixtures(projectId, userId, sourceRevisionId, targetEnvironmentId, analysis);
    }

    private DependencyAnalysisResultItemView result(
            Fixtures fixtures,
            DependencyRiskLevel riskLevel,
            String packageName,
            String targetVersion
    ) {
        return new DependencyAnalysisResultItemView(UUID.randomUUID(), fixtures.projectId, fixtures.sourceRevisionId,
                UUID.randomUUID(), fixtures.analysis.id(), DependencyType.BUILD_PACKAGE, packageName, targetVersion,
                riskLevel == DependencyRiskLevel.HIGH ? packageName : null,
                riskLevel == DependencyRiskLevel.HIGH ? "12.1.0" : null,
                null,
                targetVersion == null ? null : packageName,
                targetVersion,
                null,
                "SAME_MAJOR",
                "HIGH",
                DependencyTargetMatchStatus.REPO_AVAILABLE,
                riskLevel,
                "package:" + packageName,
                "install " + packageName,
                DependencyConfidence.HIGH,
                Map.of(),
                OffsetDateTime.now());
    }

    private SourceRevisionView sourceRevision(UUID id, UUID projectId) {
        return new SourceRevisionView(id, projectId, SourceRevisionType.GIT, "v1", null,
                "https://example.invalid/repo.git", "main", "abc", null, "/tmp/src", null,
                true, UUID.randomUUID(), OffsetDateTime.now());
    }

    private ProjectRuntimeEnvironmentResponse runtimeSummary(Fixtures fixtures) {
        SourceDeployEnvironmentSummary target = new SourceDeployEnvironmentSummary(
                fixtures.targetEnvironmentId, "target", null, "riscv64", null, true);
        return new ProjectRuntimeEnvironmentResponse(fixtures.projectId, null, target, 7L, true,
                List.of(), fixtures.userId, OffsetDateTime.now());
    }

    private TaskView task(UUID taskId, UUID projectId, UUID userId) {
        return new TaskView(taskId, projectId, RvPortTaskTypes.DEPENDENCY_AUTO_FIX, TaskStatus.PENDING,
                0, "queued", userId, OffsetDateTime.now(), OffsetDateTime.now(), null,
                null, null, null, null, 0);
    }

    private DependencyAutoFixRunView autoFixRun(Fixtures fixtures) {
        OffsetDateTime now = OffsetDateTime.now();
        return new DependencyAutoFixRunView(
                UUID.randomUUID(), fixtures.projectId, UUID.randomUUID(), fixtures.analysis.id(),
                fixtures.sourceRevisionId, fixtures.targetEnvironmentId, 7L, null, null,
                DependencyAutoFixRunStatus.SUCCEEDED, 1, 1, 0, 0, Map.of(), null,
                now, now, now);
    }

    private DependencyAutoFixItemView autoFixItem(Fixtures fixtures, UUID runId) {
        OffsetDateTime now = OffsetDateTime.now();
        return new DependencyAutoFixItemView(
                UUID.randomUUID(), runId, UUID.randomUUID(), fixtures.projectId,
                fixtures.sourceRevisionId, DependencyRiskLevel.MEDIUM,
                DependencyTargetMatchStatus.REPO_AVAILABLE, "zlib", "1.2", "zlib", "1.2",
                "zlib", "1.2", true, DependencyAutoFixItemStatus.SUCCEEDED,
                0, null, Map.of(), now, now, now);
    }

    private record Fixtures(
            UUID projectId,
            UUID userId,
            UUID sourceRevisionId,
            UUID targetEnvironmentId,
            DependencyAnalysisView analysis
    ) {
    }
}
