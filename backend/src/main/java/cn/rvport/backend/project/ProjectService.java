package cn.rvport.backend.project;

import cn.rvport.backend.audit.AuditLogService;
import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.project.runtime.ProjectRuntimeEnvironmentResponse;
import cn.rvport.backend.project.runtime.ProjectRuntimeEnvironmentService;
import cn.rvport.backend.source.SourceRevisionResponse;
import cn.rvport.backend.source.SourceService;
import cn.rvport.backend.task.TaskEventService;
import cn.rvport.backend.task.TaskRepository;
import cn.rvport.backend.task.TaskResponse;
import cn.rvport.backend.workflow.ProjectContextService;
import cn.rvport.backend.workflow.ProjectContextSnapshot;
import jakarta.servlet.http.HttpServletRequest;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ProjectService {

    private final ProjectRepository projectRepository;
    private final SourceService sourceService;
    private final ProjectRuntimeEnvironmentService projectRuntimeEnvironmentService;
    private final TaskEventService taskEventService;
    private final AuditLogService auditLogService;
    private final ProjectAccessService projectAccessService;
    private final ProjectContextService projectContextService;
    private final ProjectWorkflowStatusService workflowStatusService;
    private final TaskRepository taskRepository;

    public ProjectService(
            ProjectRepository projectRepository,
            SourceService sourceService,
            ProjectRuntimeEnvironmentService projectRuntimeEnvironmentService,
            TaskEventService taskEventService,
            AuditLogService auditLogService,
            ProjectAccessService projectAccessService,
            ProjectContextService projectContextService,
            ProjectWorkflowStatusService workflowStatusService,
            TaskRepository taskRepository
    ) {
        this.projectRepository = projectRepository;
        this.sourceService = sourceService;
        this.projectRuntimeEnvironmentService = projectRuntimeEnvironmentService;
        this.taskEventService = taskEventService;
        this.auditLogService = auditLogService;
        this.projectAccessService = projectAccessService;
        this.projectContextService = projectContextService;
        this.workflowStatusService = workflowStatusService;
        this.taskRepository = taskRepository;
    }

    @Transactional(readOnly = true)
    public PageResponse<ProjectResponse> list(ProjectListRequest request, UUID actorUserId, boolean superAdmin) {
        int page = request.normalizedPage();
        int pageSize = request.normalizedPageSize();
        long total = projectRepository.countAccessible(request.status(), request.stage(), request.keyword(), actorUserId, superAdmin);
        List<ProjectView> projects = projectRepository.listAccessible(request.status(), request.stage(), request.keyword(), page, pageSize, actorUserId, superAdmin);
        Map<UUID, ProjectSummaryView> summaries = summaries(projects.stream().map(ProjectView::id).toList());
        List<ProjectResponse> items = projects.stream()
                .map(project -> ProjectResponse.from(project, summaries.getOrDefault(project.id(), ProjectSummaryView.empty())))
                .toList();
        return PageResponse.of(items, page, pageSize, total);
    }

    @Transactional
    public ProjectResponse create(CreateProjectRequest request, UUID actorUserId, HttpServletRequest httpRequest) {
        ProjectView project = projectRepository.create(
                trim(request.name()),
                trimToNull(request.description()),
                valueOrDefault(request.sourceArch(), "x86_64"),
                valueOrDefault(request.targetArch(), "riscv64"),
                actorUserId
        );
        auditLogService.record(project.id(), actorUserId, "project.create", "project", project.id(),
                Map.of("name", project.name()), httpRequest);
        return ProjectResponse.from(project, summary(project.id()));
    }

    @Transactional(readOnly = true)
    public ProjectResponse get(UUID projectId, UUID actorUserId, boolean superAdmin) {
        ProjectView project = projectAccessService.requireProjectAccess(projectId, actorUserId, superAdmin);
        return ProjectResponse.from(project, summary(project.id()));
    }

    @Transactional
    public ProjectResponse update(UUID projectId, UpdateProjectRequest request, UUID actorUserId, boolean superAdmin, HttpServletRequest httpRequest) {
        if (request.stage() != null) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "PROJECT_STAGE_READONLY", "项目 stage 不能通过基础信息接口修改");
        }
        ProjectView current = projectAccessService.requireProjectAccess(projectId, actorUserId, superAdmin);
        ProjectView updated = projectRepository.update(
                projectId,
                valueOrCurrent(request.name(), current.name()),
                request.description() == null ? current.description() : trimToNull(request.description()),
                valueOrCurrent(request.sourceArch(), current.sourceArch()),
                valueOrCurrent(request.targetArch(), current.targetArch()),
                request.status() == null ? current.status() : request.status()
        );
        if (updated == null) {
            throw new ApiException(HttpStatus.NOT_FOUND, "PROJECT_NOT_FOUND", "项目不存在");
        }
        auditLogService.record(projectId, actorUserId, "project.update", "project", projectId,
                Map.of("name", updated.name(), "status", updated.status().name()), httpRequest);
        return ProjectResponse.from(updated, summary(updated.id()));
    }

    @Transactional(readOnly = true)
    public ProjectOverviewResponse overview(UUID projectId, UUID actorUserId, boolean superAdmin) {
        ProjectView projectView = projectAccessService.requireProjectAccess(projectId, actorUserId, superAdmin);
        long latestTaskEventId = taskEventService.latestEventId(projectId);
        ProjectResponse project = ProjectResponse.from(projectView, summary(projectId));
        SourceRevisionResponse activeSource = sourceService.activeSource(projectId);
        ProjectRuntimeEnvironmentResponse runtimeEnvironmentSummary = projectRuntimeEnvironmentService.summary(projectId);
        ProjectContextSnapshot context = projectContextService.snapshot(projectId);
        List<TaskResponse> recentTasks = taskRepository.list(projectId, null, null, 1, 5)
                .stream()
                .map(TaskResponse::from)
                .toList();
        return new ProjectOverviewResponse(
                project,
                new ProjectOverviewResponse.CurrentContextResponse(activeSource, runtimeEnvironmentSummary),
                workflowStatusService.aggregate(projectId, activeSource, runtimeEnvironmentSummary, context),
                recentTasks,
                latestTaskEventId
        );
    }

    private ProjectView requireProject(UUID projectId) {
        return projectRepository.findById(projectId)
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "PROJECT_NOT_FOUND", "项目不存在"));
    }

    private ProjectSummaryView summary(UUID projectId) {
        return summaries(List.of(projectId)).getOrDefault(projectId, ProjectSummaryView.empty());
    }

    private Map<UUID, ProjectSummaryView> summaries(List<UUID> projectIds) {
        if (projectIds.isEmpty()) {
            return Map.of();
        }
        Map<UUID, ProjectSummaryView> summaries = projectRepository.summaries(projectIds);
        return summaries == null ? Map.of() : summaries;
    }

    private String trim(String value) {
        return value == null ? null : value.trim();
    }

    private String trimToNull(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }

    private String valueOrDefault(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value.trim();
    }

    private String valueOrCurrent(String value, String current) {
        return value == null ? current : trim(value);
    }
}
