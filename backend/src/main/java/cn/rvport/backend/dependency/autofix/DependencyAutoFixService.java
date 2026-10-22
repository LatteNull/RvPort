package cn.rvport.backend.dependency.autofix;

import cn.rvport.backend.audit.AuditLogService;
import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.dependency.DependencyAnalysisRepository;
import cn.rvport.backend.dependency.DependencyAnalysisResultItemView;
import cn.rvport.backend.dependency.DependencyAnalysisView;
import cn.rvport.backend.project.ProjectAccessService;
import cn.rvport.backend.project.runtime.ProjectRuntimeEnvironmentService;
import cn.rvport.backend.source.SourceRepository;
import cn.rvport.backend.source.SourceRevisionView;
import cn.rvport.backend.task.RvPortTaskTypes;
import cn.rvport.backend.task.TaskCreateCommand;
import cn.rvport.backend.task.TaskResponse;
import cn.rvport.backend.task.TaskService;
import jakarta.servlet.http.HttpServletRequest;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class DependencyAutoFixService {

    private final DependencyAutoFixRepository repository;
    private final DependencyAnalysisRepository dependencyAnalysisRepository;
    private final ProjectRuntimeEnvironmentService runtimeEnvironmentService;
    private final SourceRepository sourceRepository;
    private final ProjectAccessService projectAccessService;
    private final TaskService taskService;
    private final AuditLogService auditLogService;
    private final DependencyAutoFixCandidatePolicy candidatePolicy = new DependencyAutoFixCandidatePolicy();

    public DependencyAutoFixService(
            DependencyAutoFixRepository repository,
            DependencyAnalysisRepository dependencyAnalysisRepository,
            ProjectRuntimeEnvironmentService runtimeEnvironmentService,
            SourceRepository sourceRepository,
            ProjectAccessService projectAccessService,
            TaskService taskService,
            AuditLogService auditLogService
    ) {
        this.repository = repository;
        this.dependencyAnalysisRepository = dependencyAnalysisRepository;
        this.runtimeEnvironmentService = runtimeEnvironmentService;
        this.sourceRepository = sourceRepository;
        this.projectAccessService = projectAccessService;
        this.taskService = taskService;
        this.auditLogService = auditLogService;
    }

    @Transactional(readOnly = true)
    public PageResponse<DependencyAutoFixCandidateResponse> candidates(
            UUID analysisId,
            DependencyAutoFixCandidateListRequest request,
            UUID actorUserId,
            boolean superAdmin
    ) {
        DependencyAnalysisView run = requireAccessibleAnalysis(analysisId, actorUserId, superAdmin);
        validateCandidateSort(request);
        List<DependencyAutoFixCandidateResponse> filtered = candidatePolicy.filterAndSort(
                dependencyAnalysisRepository.listResultItemViews(run.id()).stream()
                        .map(candidatePolicy::candidate)
                        .toList(),
                request
        );
        int page = request.normalizedPage();
        int pageSize = request.normalizedPageSize();
        int from = Math.min((page - 1) * pageSize, filtered.size());
        int to = Math.min(from + pageSize, filtered.size());
        return PageResponse.of(filtered.subList(from, to), page, pageSize, filtered.size());
    }

    @Transactional
    public DependencyAutoFixCreateResponse create(
            UUID analysisId,
            DependencyAutoFixCreateRequest request,
            UUID actorUserId,
            boolean superAdmin,
            HttpServletRequest httpRequest
    ) {
        if (request == null || request.resultItemIds() == null || request.resultItemIds().isEmpty()) {
            throw badRequest("DEPENDENCY_AUTO_FIX_ITEMS_REQUIRED", "自动修复条目不能为空");
        }
        DependencyAnalysisView run = requireAccessibleAnalysis(analysisId, actorUserId, superAdmin);
        requireCurrentContext(run);
        List<UUID> uniqueIds = deduplicate(request.resultItemIds());
        Map<UUID, DependencyAutoFixCandidateResponse> candidatesById = new LinkedHashMap<>();
        for (DependencyAnalysisResultItemView item : dependencyAnalysisRepository.listResultItemViews(run.id())) {
            DependencyAutoFixCandidateResponse candidate = candidatePolicy.candidate(item);
            if (candidate.selectable()) {
                candidatesById.put(candidate.resultItemId(), candidate);
            }
        }
        List<DependencyAutoFixCandidateResponse> selected = new ArrayList<>();
        for (UUID itemId : uniqueIds) {
            DependencyAutoFixCandidateResponse candidate = candidatesById.get(itemId);
            if (candidate == null) {
                throw badRequest("DEPENDENCY_AUTO_FIX_ITEM_INVALID", "自动修复条目不存在或不可自动修复");
            }
            selected.add(candidate);
        }
        UUID autoFixRunId = UUID.randomUUID();
        Map<String, Object> input = new LinkedHashMap<>();
        input.put("projectId", run.projectId());
        input.put("autoFixRunId", autoFixRunId);
        input.put("dependencyAnalysisRunId", run.id());
        input.put("sourceRevisionId", run.sourceRevisionId());
        input.put("targetEnvironmentId", run.targetEnvironmentId());
        input.put("environmentConfigVersion", run.environmentConfigVersion());
        input.put("rerunDependencyAnalysis", request.shouldRerunDependencyAnalysis());
        TaskResponse task = taskService.create(new TaskCreateCommand(
                run.projectId(),
                RvPortTaskTypes.DEPENDENCY_AUTO_FIX,
                input,
                actorUserId,
                null,
                "依赖自动修复任务已创建"
        ));
        repository.createRun(autoFixRunId, run.projectId(), task.id(), run.id(), run.sourceRevisionId(),
                run.targetEnvironmentId(), run.environmentConfigVersion(), selected.size());
        repository.createItems(autoFixRunId, selected, run.projectId(), run.sourceRevisionId());
        auditLogService.record(run.projectId(), actorUserId, "dependency.auto_fix.create", "dependency_auto_fix_run", autoFixRunId,
                Map.of(
                        "taskId", task.id(),
                        "dependencyAnalysisRunId", run.id(),
                        "sourceRevisionId", run.sourceRevisionId(),
                        "targetEnvironmentId", run.targetEnvironmentId(),
                        "environmentConfigVersion", run.environmentConfigVersion(),
                        "selectedCount", selected.size()
                ), httpRequest);
        return new DependencyAutoFixCreateResponse(autoFixRunId, task.id(), selected.size(), task);
    }

    @Transactional(readOnly = true)
    public DependencyAutoFixRunResponse get(UUID autoFixRunId, UUID actorUserId, boolean superAdmin) {
        DependencyAutoFixRunView run = requireAccessibleRun(autoFixRunId, actorUserId, superAdmin);
        return DependencyAutoFixRunResponse.from(run);
    }

    @Transactional(readOnly = true)
    public PageResponse<DependencyAutoFixRunResponse> list(UUID projectId, DependencyAutoFixRunListRequest request,
                                                           UUID actorUserId, boolean superAdmin) {
        projectAccessService.requireProjectAccess(projectId, actorUserId, superAdmin);
        validateRunSort(request);
        DependencyAutoFixRunListRequest effective = currentRequest(projectId, request);
        long total = repository.countRuns(projectId, effective);
        List<DependencyAutoFixRunResponse> items = repository.listRuns(projectId, effective).stream()
                .map(DependencyAutoFixRunResponse::from)
                .toList();
        return PageResponse.of(items, effective.normalizedPage(), effective.normalizedPageSize(), total);
    }

    @Transactional(readOnly = true)
    public PageResponse<DependencyAutoFixItemResponse> items(UUID autoFixRunId, DependencyAutoFixItemListRequest request,
                                                             UUID actorUserId, boolean superAdmin) {
        DependencyAutoFixRunView run = requireAccessibleRun(autoFixRunId, actorUserId, superAdmin);
        validateItemSort(request);
        long total = repository.countItems(run.id(), request);
        List<DependencyAutoFixItemResponse> items = repository.listItems(run.id(), request).stream()
                .map(DependencyAutoFixItemResponse::from)
                .toList();
        return PageResponse.of(items, request.normalizedPage(), request.normalizedPageSize(), total);
    }

    private DependencyAnalysisView requireAccessibleAnalysis(UUID analysisId, UUID actorUserId, boolean superAdmin) {
        DependencyAnalysisView run = dependencyAnalysisRepository.findById(analysisId)
                .orElseThrow(() -> notFound("DEPENDENCY_ANALYSIS_NOT_FOUND", "依赖分析不存在"));
        projectAccessService.requireProjectAccess(run.projectId(), actorUserId, superAdmin);
        return run;
    }

    private DependencyAutoFixRunView requireAccessibleRun(UUID autoFixRunId, UUID actorUserId, boolean superAdmin) {
        DependencyAutoFixRunView run = repository.findRun(autoFixRunId)
                .orElseThrow(() -> notFound("DEPENDENCY_AUTO_FIX_NOT_FOUND", "依赖自动修复运行不存在"));
        projectAccessService.requireProjectAccess(run.projectId(), actorUserId, superAdmin);
        return run;
    }

    private void requireCurrentContext(DependencyAnalysisView run) {
        UUID activeSourceRevisionId = sourceRepository.findActive(run.projectId()).map(SourceRevisionView::id).orElse(null);
        long currentVersion = runtimeEnvironmentService.currentVersion(run.projectId());
        if (!Objects.equals(activeSourceRevisionId, run.sourceRevisionId()) || currentVersion != run.environmentConfigVersion()) {
            throw badRequest("DEPENDENCY_AUTO_FIX_ANALYSIS_STALE", "依赖分析结果已过期，请重新运行依赖分析");
        }
        var runtime = runtimeEnvironmentService.summary(run.projectId());
        if (!runtime.ready() || runtime.targetEnvironment() == null || !Objects.equals(runtime.targetEnvironment().id(), run.targetEnvironmentId())) {
            throw badRequest("DEPENDENCY_AUTO_FIX_TARGET_ENVIRONMENT_STALE", "目标运行环境已变更，请重新运行依赖分析");
        }
    }

    private DependencyAutoFixRunListRequest currentRequest(UUID projectId, DependencyAutoFixRunListRequest request) {
        if (request.includeStaleEffective() || request.sourceRevisionId() != null || request.environmentConfigVersion() != null) {
            return request;
        }
        UUID activeSourceRevisionId = sourceRepository.findActive(projectId).map(SourceRevisionView::id).orElse(null);
        return new DependencyAutoFixRunListRequest(
                request.page(),
                request.pageSize(),
                activeSourceRevisionId,
                runtimeEnvironmentService.currentVersion(projectId),
                request.includeStale(),
                request.status(),
                request.sortBy(),
                request.sortDirection()
        );
    }

    private List<UUID> deduplicate(List<UUID> ids) {
        Set<UUID> seen = new LinkedHashSet<>(ids);
        if (seen.size() != ids.size()) {
            throw badRequest("DEPENDENCY_AUTO_FIX_ITEM_DUPLICATED", "自动修复条目不能重复");
        }
        return new ArrayList<>(seen);
    }

    private void validateCandidateSort(DependencyAutoFixCandidateListRequest request) {
        if (!candidatePolicy.isAllowedSort(request.sortBy())) {
            throw badRequest("DEPENDENCY_AUTO_FIX_QUERY_INVALID", "自动修复候选排序字段不正确");
        }
        validateSortDirection(request.sortDirection(), "DEPENDENCY_AUTO_FIX_QUERY_INVALID");
    }

    private void validateRunSort(DependencyAutoFixRunListRequest request) {
        String sortBy = request.sortBy();
        if (sortBy != null && !sortBy.isBlank()
                && !List.of("createdAt", "startedAt", "finishedAt", "status").contains(sortBy.trim())) {
            throw badRequest("DEPENDENCY_AUTO_FIX_QUERY_INVALID", "自动修复排序字段不正确");
        }
        validateSortDirection(request.sortDirection(), "DEPENDENCY_AUTO_FIX_QUERY_INVALID");
    }

    private void validateItemSort(DependencyAutoFixItemListRequest request) {
        String sortBy = request.sortBy();
        if (sortBy != null && !sortBy.isBlank()
                && !List.of("createdAt", "finishedAt", "status", "riskLevel", "targetMatchStatus", "installPackageName").contains(sortBy.trim())) {
            throw badRequest("DEPENDENCY_AUTO_FIX_QUERY_INVALID", "自动修复条目排序字段不正确");
        }
        validateSortDirection(request.sortDirection(), "DEPENDENCY_AUTO_FIX_QUERY_INVALID");
    }

    private void validateSortDirection(String direction, String errorCode) {
        if (direction != null && !direction.isBlank() && !List.of("asc", "desc").contains(direction.trim().toLowerCase())) {
            throw badRequest(errorCode, "排序方向不正确");
        }
    }

    private ApiException notFound(String code, String message) {
        return new ApiException(HttpStatus.NOT_FOUND, code, message);
    }

    private ApiException badRequest(String code, String message) {
        return new ApiException(HttpStatus.BAD_REQUEST, code, message);
    }
}
