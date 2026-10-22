package cn.rvport.backend.source.deploy;

import cn.rvport.backend.audit.AuditLogService;
import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.environment.EnvironmentRepository;
import cn.rvport.backend.environment.EnvironmentView;
import cn.rvport.backend.project.ProjectAccessService;
import cn.rvport.backend.project.runtime.ProjectRuntimeEnvironmentService;
import cn.rvport.backend.project.runtime.ProjectRuntimeEnvironmentView;
import cn.rvport.backend.source.SourceRepository;
import cn.rvport.backend.source.SourceRevisionResponse;
import cn.rvport.backend.source.SourceRevisionView;
import cn.rvport.backend.task.RvPortTaskTypes;
import cn.rvport.backend.task.TaskCreateCommand;
import cn.rvport.backend.task.TaskRepository;
import cn.rvport.backend.task.TaskResponse;
import cn.rvport.backend.task.TaskService;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class SourceDeployService {

    private static final int DEFAULT_TIMEOUT_SECONDS = 3600;

    private final SourceDeployRepository sourceDeployRepository;
    private final SourceRepository sourceRepository;
    private final EnvironmentRepository environmentRepository;
    private final ProjectRuntimeEnvironmentService projectRuntimeEnvironmentService;
    private final ProjectAccessService projectAccessService;
    private final TaskService taskService;
    private final TaskRepository taskRepository;
    private final AuditLogService auditLogService;
    private final ObjectMapper objectMapper;

    public SourceDeployService(
            SourceDeployRepository sourceDeployRepository,
            SourceRepository sourceRepository,
            EnvironmentRepository environmentRepository,
            ProjectRuntimeEnvironmentService projectRuntimeEnvironmentService,
            ProjectAccessService projectAccessService,
            TaskService taskService,
            TaskRepository taskRepository,
            AuditLogService auditLogService,
            ObjectMapper objectMapper
    ) {
        this.sourceDeployRepository = sourceDeployRepository;
        this.sourceRepository = sourceRepository;
        this.environmentRepository = environmentRepository;
        this.projectRuntimeEnvironmentService = projectRuntimeEnvironmentService;
        this.projectAccessService = projectAccessService;
        this.taskService = taskService;
        this.taskRepository = taskRepository;
        this.auditLogService = auditLogService;
        this.objectMapper = objectMapper;
    }

    @Transactional
    public SourceDeployCreateResponse create(
            UUID projectId,
            SourceDeployCreateRequest request,
            UUID actorUserId,
            boolean superAdmin,
            HttpServletRequest httpRequest
    ) {
        projectAccessService.requireProjectAccess(projectId, actorUserId, superAdmin);
        SourceRevisionView sourceRevision = requireSourceRevision(projectId, request.sourceRevisionId());
        validateWorkingCopy(sourceRevision);
        if (request.environmentIds() != null && !request.environmentIds().isEmpty()) {
            throw badRequest("SOURCE_DEPLOY_ENVIRONMENTS_DEPRECATED", "源码部署环境由项目运行环境配置决定，不能在请求中指定");
        }
        ProjectRuntimeEnvironmentView runtimeEnvironments = projectRuntimeEnvironmentService.requireComplete(projectId, actorUserId, superAdmin);
        List<UUID> environmentIds = List.of(runtimeEnvironments.sourceEnvironmentId(), runtimeEnvironments.targetEnvironmentId());

        List<SourceDeployResponse> deployments = environmentIds.stream()
                .map(environmentId -> createOne(projectId, sourceRevision, environmentId, runtimeEnvironments.version(), request, actorUserId, httpRequest))
                .toList();
        return new SourceDeployCreateResponse(deployments);
    }

    @Transactional(readOnly = true)
    public PageResponse<SourceDeployResponse> list(UUID projectId, SourceDeployListRequest request, UUID actorUserId, boolean superAdmin) {
        projectAccessService.requireProjectAccess(projectId, actorUserId, superAdmin);
        validateSort(request);
        long total = sourceDeployRepository.count(projectId, request);
        List<SourceDeployResponse> items = sourceDeployRepository.list(projectId, request)
                .stream()
                .map(this::response)
                .toList();
        return PageResponse.of(items, request.normalizedPage(), request.normalizedPageSize(), total);
    }

    @Transactional(readOnly = true)
    public SourceDeployResponse get(UUID sourceDeploymentId, UUID actorUserId, boolean superAdmin) {
        SourceDeployRunView run = requireAccessible(sourceDeploymentId, actorUserId, superAdmin);
        return response(run);
    }

    @Transactional
    public TaskResponse cancel(UUID sourceDeploymentId, UUID actorUserId, boolean superAdmin) {
        SourceDeployRunView run = requireAccessible(sourceDeploymentId, actorUserId, superAdmin);
        TaskResponse task = taskService.cancel(run.taskId(), actorUserId, superAdmin);
        sourceDeployRepository.syncStatusByTask(run.taskId(), task.status());
        return task;
    }

    private SourceDeployResponse createOne(
            UUID projectId,
            SourceRevisionView sourceRevision,
            UUID environmentId,
            long environmentConfigVersion,
            SourceDeployCreateRequest request,
            UUID actorUserId,
            HttpServletRequest httpRequest
    ) {
        EnvironmentView environment = requireEnvironment(projectId, environmentId);
        String remotePath = remotePath(environment, sourceRevision.id());
        if (!request.forceValue()) {
            var reusable = sourceDeployRepository.findReusable(projectId, sourceRevision.id(), environment.id(), environmentConfigVersion);
            if (reusable.isPresent()) {
                return response(reusable.get());
            }
        }

        UUID sourceDeploymentId = UUID.randomUUID();
        Map<String, Object> input = new LinkedHashMap<>();
        input.put("projectId", projectId);
        input.put("sourceDeploymentId", sourceDeploymentId);
        input.put("sourceRevisionId", sourceRevision.id());
        input.put("environmentId", environment.id());
        input.put("environmentConfigVersion", environmentConfigVersion);
        input.put("force", request.forceValue());
        input.put("timeoutSeconds", effectiveTimeout(request.timeoutSeconds()));

        TaskResponse task = taskService.create(new TaskCreateCommand(
                projectId,
                RvPortTaskTypes.SOURCE_DEPLOY,
                input,
                actorUserId,
                effectiveTimeout(request.timeoutSeconds()),
                "源码部署任务已创建"
        ));
        SourceDeployRunView run = sourceDeployRepository.createPending(
                sourceDeploymentId,
                projectId,
                task.id(),
                sourceRevision.id(),
                environment.id(),
                environmentConfigVersion,
                remotePath,
                request.forceValue()
        );
        auditLogService.record(projectId, actorUserId, "source.deploy.create", "source_deploy_run", run.id(),
                Map.of("taskId", task.id(), "sourceRevisionId", sourceRevision.id(), "environmentId", environment.id(), "force", request.forceValue()), httpRequest);
        return response(run);
    }

    private SourceDeployRunView requireAccessible(UUID sourceDeploymentId, UUID actorUserId, boolean superAdmin) {
        SourceDeployRunView run = sourceDeployRepository.findById(sourceDeploymentId)
                .orElseThrow(() -> notFound("SOURCE_DEPLOYMENT_NOT_FOUND", "源码部署记录不存在"));
        projectAccessService.requireProjectAccess(run.projectId(), actorUserId, superAdmin);
        return run;
    }

    private SourceRevisionView requireSourceRevision(UUID projectId, UUID sourceRevisionId) {
        SourceRevisionView revision = sourceRepository.findById(sourceRevisionId)
                .orElseThrow(() -> notFound("SOURCE_REVISION_NOT_FOUND", "源码版本不存在"));
        if (!Objects.equals(revision.projectId(), projectId)) {
            throw notFound("SOURCE_REVISION_NOT_FOUND", "源码版本不存在");
        }
        return revision;
    }

    private EnvironmentView requireEnvironment(UUID projectId, UUID environmentId) {
        EnvironmentView environment = environmentRepository.findById(environmentId)
                .orElseThrow(() -> notFound("ENVIRONMENT_NOT_FOUND", "环境不存在"));
        if (!Objects.equals(environment.projectId(), projectId)) {
            throw notFound("ENVIRONMENT_NOT_FOUND", "环境不存在");
        }
        if (!environment.enabled()) {
            throw badRequest("ENVIRONMENT_DISABLED", "环境已禁用");
        }
        if (environment.workingDirectory() == null || environment.workingDirectory().isBlank()) {
            throw badRequest("ENVIRONMENT_WORKING_DIRECTORY_REQUIRED", "环境工作目录不能为空");
        }
        return environment;
    }

    private void validateWorkingCopy(SourceRevisionView sourceRevision) {
        if (sourceRevision.workingCopyPath() == null || sourceRevision.workingCopyPath().isBlank()) {
            throw badRequest("SOURCE_REVISION_WORKING_COPY_NOT_FOUND", "源码工作副本不存在");
        }
        if (!Files.isDirectory(Path.of(sourceRevision.workingCopyPath()))) {
            throw badRequest("SOURCE_REVISION_WORKING_COPY_NOT_FOUND", "源码工作副本不存在");
        }
    }

    private SourceDeployResponse response(SourceDeployRunView run) {
        SourceRevisionResponse sourceRevision = sourceRepository.findById(run.sourceRevisionId())
                .map(SourceRevisionResponse::from)
                .orElse(null);
        SourceDeployEnvironmentSummary environment = environmentRepository.findById(run.environmentId())
                .map(SourceDeployEnvironmentSummary::from)
                .orElse(null);
        long currentVersion = projectRuntimeEnvironmentService.currentVersion(run.projectId());
        return SourceDeployResponse.from(run, sourceRevision, environment, objectMapper, currentVersion);
    }

    private String remotePath(EnvironmentView environment, UUID sourceRevisionId) {
        String root = environment.workingDirectory().replace('\\', '/').replaceAll("/+$", "");
        return root + "/rvport-sources/" + sourceRevisionId;
    }

    private int effectiveTimeout(Integer timeoutSeconds) {
        return timeoutSeconds == null ? DEFAULT_TIMEOUT_SECONDS : timeoutSeconds;
    }

    private void validateSort(SourceDeployListRequest request) {
        String sortBy = request.sortBy();
        if (sortBy != null && !sortBy.isBlank() && !List.of("createdAt", "startedAt", "finishedAt", "status").contains(sortBy.trim())) {
            throw badRequest("SOURCE_DEPLOY_QUERY_INVALID", "源码部署排序字段不正确");
        }
        String direction = request.sortDirection();
        if (direction != null && !direction.isBlank() && !List.of("asc", "desc").contains(direction.trim().toLowerCase())) {
            throw badRequest("SOURCE_DEPLOY_QUERY_INVALID", "源码部署排序方向不正确");
        }
    }

    private ApiException notFound(String code, String message) {
        return new ApiException(HttpStatus.NOT_FOUND, code, message);
    }

    private ApiException badRequest(String code, String message) {
        return new ApiException(HttpStatus.BAD_REQUEST, code, message);
    }
}
