package cn.rvport.backend.dependency;

import cn.rvport.backend.artifact.StoredArtifactOwnerType;
import cn.rvport.backend.artifact.StoredArtifactRepository;
import cn.rvport.backend.artifact.StoredArtifactResource;
import cn.rvport.backend.artifact.StoredArtifactService;
import cn.rvport.backend.artifact.StoredArtifactView;
import cn.rvport.backend.audit.AuditLogService;
import cn.rvport.backend.buildvalidation.BuildValidationRepository;
import cn.rvport.backend.buildvalidation.BuildValidationRunView;
import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.migration.MigrationInputSourceType;
import cn.rvport.backend.migration.NodeReportInclusionService;
import cn.rvport.backend.migration.NodeReportInclusionState;
import cn.rvport.backend.project.ProjectAccessService;
import cn.rvport.backend.project.runtime.ProjectRuntimeEnvironmentService;
import cn.rvport.backend.project.runtime.ProjectRuntimeEnvironmentView;
import cn.rvport.backend.source.SourceRepository;
import cn.rvport.backend.source.SourceRevisionView;
import cn.rvport.backend.task.RvPortTaskTypes;
import cn.rvport.backend.task.TaskCreateCommand;
import cn.rvport.backend.task.TaskRepository;
import cn.rvport.backend.task.TaskResponse;
import cn.rvport.backend.task.TaskService;
import cn.rvport.backend.workflow.DomainLatestExecutionResponse;
import cn.rvport.backend.workflow.DomainLatestResponse;
import cn.rvport.backend.workflow.ProjectContextService;
import cn.rvport.backend.workflow.ProjectContextSnapshot;
import cn.rvport.backend.workflow.StageIds;
import cn.rvport.backend.workflow.StagePrerequisiteKeys;
import cn.rvport.backend.workflow.StageReadinessService;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class DependencyAnalysisService {

    private final DependencyAnalysisRepository repository;
    private final BuildValidationRepository buildValidationRepository;
    private final ProjectRuntimeEnvironmentService runtimeEnvironmentService;
    private final SourceRepository sourceRepository;
    private final ProjectAccessService projectAccessService;
    private final TaskService taskService;
    private final TaskRepository taskRepository;
    private final ProjectContextService projectContextService;
    private final StageReadinessService stageReadinessService;
    private final AuditLogService auditLogService;
    private final StoredArtifactRepository storedArtifactRepository;
    private final StoredArtifactService storedArtifactService;
    private final ObjectMapper objectMapper;
    private final NodeReportInclusionService nodeReportInclusionService;

    public DependencyAnalysisService(
            DependencyAnalysisRepository repository,
            BuildValidationRepository buildValidationRepository,
            ProjectRuntimeEnvironmentService runtimeEnvironmentService,
            SourceRepository sourceRepository,
            ProjectAccessService projectAccessService,
            TaskService taskService,
            TaskRepository taskRepository,
            ProjectContextService projectContextService,
            StageReadinessService stageReadinessService,
            AuditLogService auditLogService,
            StoredArtifactRepository storedArtifactRepository,
            StoredArtifactService storedArtifactService,
            ObjectMapper objectMapper,
            NodeReportInclusionService nodeReportInclusionService
    ) {
        this.repository = repository;
        this.buildValidationRepository = buildValidationRepository;
        this.runtimeEnvironmentService = runtimeEnvironmentService;
        this.sourceRepository = sourceRepository;
        this.projectAccessService = projectAccessService;
        this.taskService = taskService;
        this.taskRepository = taskRepository;
        this.projectContextService = projectContextService;
        this.stageReadinessService = stageReadinessService;
        this.auditLogService = auditLogService;
        this.storedArtifactRepository = storedArtifactRepository;
        this.storedArtifactService = storedArtifactService;
        this.objectMapper = objectMapper;
        this.nodeReportInclusionService = nodeReportInclusionService;
    }

    @Transactional
    public DependencyAnalysisCreateResponse create(UUID projectId, DependencyAnalysisCreateRequest request,
                                                   UUID actorUserId, boolean superAdmin, HttpServletRequest httpRequest) {
        projectAccessService.requireProjectAccess(projectId, actorUserId, superAdmin);
        stageReadinessService.requireSatisfied(
                projectId,
                StageIds.RV_DEPENDENCY_ANALYSIS,
                List.of(StagePrerequisiteKeys.X86_BUILD, StagePrerequisiteKeys.TARGET_ENVIRONMENT),
                actorUserId,
                superAdmin
        );
        ProjectRuntimeEnvironmentView runtime = runtimeEnvironmentService.requireComplete(projectId, actorUserId, superAdmin);
        SourceRevisionView sourceRevision = requireRequestedOrActiveSourceRevision(projectId, request == null ? null : request.sourceRevisionId());
        BuildValidationRunView sourceBuild = buildValidationRepository.findLatestSucceededSourceBuild(
                        projectId,
                        sourceRevision.id(),
                        runtime.sourceEnvironmentId(),
                        runtime.version())
                .orElseThrow(() -> badRequest("DEPENDENCY_SOURCE_BUILD_REQUIRED", "当前源码版本缺少成功的 source/x86 构建运行"));
        UUID runId = UUID.randomUUID();
        Map<String, Object> input = new LinkedHashMap<>();
        input.put("projectId", projectId);
        input.put("analysisRunId", runId);
        input.put("sourceRevisionId", sourceRevision.id());
        input.put("sourceBuildRunId", sourceBuild.id());
        input.put("targetEnvironmentId", runtime.targetEnvironmentId());
        input.put("environmentConfigVersion", runtime.version());
        TaskResponse task = taskService.create(new TaskCreateCommand(
                projectId,
                RvPortTaskTypes.DEPENDENCY_ANALYSIS,
                input,
                actorUserId,
                null,
                "依赖分析任务已创建"
        ));
        repository.createRun(runId, projectId, task.id(), sourceRevision.id(), sourceBuild.id(), runtime.targetEnvironmentId(), runtime.version());
        auditLogService.record(projectId, actorUserId, "dependency.analysis.create", "dependency_analysis_run", runId,
                Map.of(
                        "taskId", task.id(),
                        "sourceRevisionId", sourceRevision.id(),
                        "sourceBuildRunId", sourceBuild.id(),
                        "targetEnvironmentId", runtime.targetEnvironmentId(),
                        "environmentConfigVersion", runtime.version()
                ), httpRequest);
        return new DependencyAnalysisCreateResponse(runId, task.id(), sourceRevision.id(), sourceBuild.id(), task);
    }

    @Transactional(readOnly = true)
    public PageResponse<DependencyAnalysisResponse> list(UUID projectId, DependencyAnalysisListRequest request,
                                                         UUID actorUserId, boolean superAdmin) {
        projectAccessService.requireProjectAccess(projectId, actorUserId, superAdmin);
        validateRunSort(request);
        DependencyAnalysisListRequest effectiveRequest = currentRequest(projectId, request);
        if (effectiveRequest == null) {
            return PageResponse.of(List.of(), request.normalizedPage(), request.normalizedPageSize(), 0);
        }
        long total = repository.countRuns(projectId, effectiveRequest);
        long currentVersion = runtimeEnvironmentService.currentVersion(projectId);
        UUID activeSourceRevisionId = sourceRepository.findActive(projectId).map(SourceRevisionView::id).orElse(null);
        List<DependencyAnalysisResponse> items = repository.listRuns(projectId, effectiveRequest).stream()
                .map(run -> DependencyAnalysisResponse.from(run, currentVersion, Objects.equals(run.sourceRevisionId(), activeSourceRevisionId)))
                .toList();
        return PageResponse.of(items, effectiveRequest.normalizedPage(), effectiveRequest.normalizedPageSize(), total);
    }

    @Transactional(readOnly = true)
    public DependencyAnalysisResponse get(UUID analysisId, UUID actorUserId, boolean superAdmin) {
        DependencyAnalysisView run = requireAccessibleRun(analysisId, actorUserId, superAdmin);
        UUID activeSourceRevisionId = sourceRepository.findActive(run.projectId()).map(SourceRevisionView::id).orElse(null);
        return DependencyAnalysisResponse.from(run, runtimeEnvironmentService.currentVersion(run.projectId()), Objects.equals(run.sourceRevisionId(), activeSourceRevisionId));
    }

    @Transactional(readOnly = true)
    public DomainLatestResponse<DependencyAnalysisResponse> latest(UUID projectId, UUID actorUserId, boolean superAdmin) {
        projectAccessService.requireProjectAccess(projectId, actorUserId, superAdmin);
        ProjectContextSnapshot context = projectContextService.snapshot(projectId);
        return repository.findLatestRun(projectId, context.sourceRevisionId(), context.runtimeEnvironmentVersion())
                .map(run -> DomainLatestResponse.current(
                        context,
                        DomainLatestExecutionResponse.from(run.id(), taskRepository.findById(run.taskId()).orElse(null)),
                        DependencyAnalysisResponse.from(run, context.runtimeEnvironmentVersion(), true)))
                .orElseGet(() -> repository.findLatestRun(projectId, null, null)
                        .map(run -> DomainLatestResponse.stale(
                                context,
                                DomainLatestExecutionResponse.from(run.id(), taskRepository.findById(run.taskId()).orElse(null)),
                                DependencyAnalysisResponse.from(run, context.runtimeEnvironmentVersion(), false)))
                        .orElseGet(() -> DomainLatestResponse.empty(context)));
    }

    @Transactional(readOnly = true)
    public PageResponse<DependencyAnalysisResultItemResponse> results(UUID analysisId, DependencyAnalysisResultListRequest request,
                                                                      UUID actorUserId, boolean superAdmin) {
        DependencyAnalysisView run = requireAccessibleRun(analysisId, actorUserId, superAdmin);
        validateResultSort(request);
        long total = repository.countResultItems(run.id(), request);
        List<DependencyAnalysisResultItemResponse> rawItems = repository.listResultItems(run.id(), request);
        Map<UUID, NodeReportInclusionState> states = nodeReportInclusionService.states(
                run.projectId(),
                run.sourceRevisionId(),
                MigrationInputSourceType.DEPENDENCY_RESULT,
                rawItems.stream().map(DependencyAnalysisResultItemResponse::id).toList()
        );
        Map<UUID, NodeReportInclusionState> inclusionStates = states == null ? Map.of() : states;
        List<DependencyAnalysisResultItemResponse> items = rawItems.stream()
                .map(item -> item.withInclusion(inclusionStates.get(item.id())))
                .toList();
        return PageResponse.of(items, request.normalizedPage(), request.normalizedPageSize(), total);
    }

    @Transactional(readOnly = true)
    public DependencyAnalysisResultItemResponse result(UUID itemId, UUID actorUserId, boolean superAdmin) {
        DependencyAnalysisResultItemView item = repository.findResultItem(itemId)
                .orElseThrow(() -> notFound("DEPENDENCY_RESULT_NOT_FOUND", "依赖分析结果不存在"));
        projectAccessService.requireProjectAccess(item.projectId(), actorUserId, superAdmin);
        NodeReportInclusionState state = nodeReportInclusionService.state(
                item.projectId(),
                item.sourceRevisionId(),
                MigrationInputSourceType.DEPENDENCY_RESULT,
                item.id()
        );
        return DependencyAnalysisResultItemResponse.from(item, state);
    }

    @Transactional(readOnly = true)
    public List<DependencyAnalysisArtifactResponse> artifacts(UUID analysisId, UUID actorUserId, boolean superAdmin) {
        DependencyAnalysisView run = requireAccessibleRun(analysisId, actorUserId, superAdmin);
        return storedArtifactRepository.listByOwner(StoredArtifactOwnerType.DEPENDENCY_ANALYSIS, run.id())
                .stream()
                .map(this::artifactResponse)
                .toList();
    }

    @Transactional(readOnly = true)
    public DependencyAnalysisArtifactDetailResponse artifact(UUID analysisId, String artifactType, UUID actorUserId, boolean superAdmin) {
        DependencyAnalysisView run = requireAccessibleRun(analysisId, actorUserId, superAdmin);
        StoredArtifactView artifact = storedArtifactRepository.findByOwner(
                        StoredArtifactOwnerType.DEPENDENCY_ANALYSIS,
                        run.id(),
                        artifactType)
                .orElseThrow(() -> notFound("DEPENDENCY_ARTIFACT_NOT_FOUND", "依赖分析制品不存在"));
        StoredArtifactResource resource = storedArtifactService.download(artifact.id());
        Object content = content(artifact.contentType(), resource);
        return new DependencyAnalysisArtifactDetailResponse(artifactResponse(artifact), content);
    }

    private SourceRevisionView requireRequestedOrActiveSourceRevision(UUID projectId, UUID requestedSourceRevisionId) {
        if (requestedSourceRevisionId != null) {
            SourceRevisionView revision = sourceRepository.findById(requestedSourceRevisionId)
                    .orElseThrow(() -> notFound("SOURCE_REVISION_NOT_FOUND", "源码版本不存在"));
            if (!revision.projectId().equals(projectId)) {
                throw notFound("SOURCE_REVISION_NOT_FOUND", "源码版本不存在");
            }
            return revision;
        }
        return sourceRepository.findActive(projectId)
                .orElseThrow(() -> badRequest("SOURCE_REVISION_REQUIRED", "项目没有当前源码版本"));
    }

    private DependencyAnalysisListRequest currentRequest(UUID projectId, DependencyAnalysisListRequest request) {
        if (!request.effectiveCurrentOnly()) {
            return request;
        }
        UUID activeSourceRevisionId = sourceRepository.findActive(projectId)
                .map(SourceRevisionView::id)
                .orElse(null);
        if (activeSourceRevisionId == null && request.sourceRevisionId() == null) {
            return null;
        }
        return request.withCurrentContext(activeSourceRevisionId, runtimeEnvironmentService.currentVersion(projectId));
    }

    private DependencyAnalysisView requireAccessibleRun(UUID analysisId, UUID actorUserId, boolean superAdmin) {
        DependencyAnalysisView run = repository.findById(analysisId)
                .orElseThrow(() -> notFound("DEPENDENCY_ANALYSIS_NOT_FOUND", "依赖分析不存在"));
        projectAccessService.requireProjectAccess(run.projectId(), actorUserId, superAdmin);
        return run;
    }

    private DependencyAnalysisArtifactResponse artifactResponse(StoredArtifactView artifact) {
        return new DependencyAnalysisArtifactResponse(
                artifact.id(),
                artifact.artifactType(),
                artifact.contentType(),
                artifact.sizeBytes(),
                artifact.sha256(),
                artifact.summary(),
                artifact.createdAt()
        );
    }

    private Object content(String contentType, StoredArtifactResource resource) {
        try {
            byte[] bytes = resource.resource().getContentAsByteArray();
            if (contentType != null && contentType.toLowerCase().contains("json")) {
                return objectMapper.readValue(bytes, new TypeReference<Map<String, Object>>() {
                });
            }
            return new String(bytes, StandardCharsets.UTF_8);
        } catch (Exception ex) {
            throw notFound("DEPENDENCY_ARTIFACT_OBJECT_NOT_FOUND", "依赖分析制品对象不存在或不可读取");
        }
    }

    private void validateRunSort(DependencyAnalysisListRequest request) {
        String sortBy = request.sortBy();
        if (sortBy != null && !sortBy.isBlank()
                && !List.of("createdAt", "startedAt", "finishedAt", "status").contains(sortBy.trim())) {
            throw badRequest("DEPENDENCY_ANALYSIS_QUERY_INVALID", "依赖分析排序字段不正确");
        }
        validateSortDirection(request.sortDirection(), "DEPENDENCY_ANALYSIS_QUERY_INVALID");
    }

    private void validateResultSort(DependencyAnalysisResultListRequest request) {
        String sortBy = request.sortBy();
        if (sortBy != null && !sortBy.isBlank()
                && !List.of("createdAt", "dependencyType", "dependencyName", "targetMatchStatus", "riskLevel").contains(sortBy.trim())) {
            throw badRequest("DEPENDENCY_RESULT_QUERY_INVALID", "依赖分析结果排序字段不正确");
        }
        validateSortDirection(request.sortDirection(), "DEPENDENCY_RESULT_QUERY_INVALID");
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
