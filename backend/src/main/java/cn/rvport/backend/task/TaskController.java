package cn.rvport.backend.task;

import cn.rvport.backend.audit.AuditLogService;
import cn.rvport.backend.common.web.ApiResponse;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.common.web.TraceIdFilter;
import cn.rvport.backend.project.ProjectAccessService;
import cn.rvport.backend.security.RvPortUserPrincipal;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import java.util.Map;
import java.util.UUID;
import org.springframework.core.io.Resource;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@Validated
public class TaskController {

    private final TaskService taskService;
    private final TaskLogService taskLogService;
    private final TaskLogIncrementService taskLogIncrementService;
    private final AuditLogService auditLogService;
    private final ProjectAccessService projectAccessService;

    public TaskController(TaskService taskService, TaskLogService taskLogService, TaskLogIncrementService taskLogIncrementService, AuditLogService auditLogService, ProjectAccessService projectAccessService) {
        this.taskService = taskService;
        this.taskLogService = taskLogService;
        this.taskLogIncrementService = taskLogIncrementService;
        this.auditLogService = auditLogService;
        this.projectAccessService = projectAccessService;
    }

    @GetMapping("/api/projects/{projectId}/tasks")
    public ApiResponse<PageResponse<TaskResponse>> listProjectTasks(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @Valid @ModelAttribute TaskListRequest query,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(taskService.list(projectId, query, principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/tasks/{taskId}")
    public ApiResponse<TaskResponse> get(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID taskId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(taskService.get(taskId, principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @PostMapping("/api/tasks/{taskId}/cancel")
    public ApiResponse<TaskResponse> cancel(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID taskId,
            HttpServletRequest request
    ) {
        TaskResponse response = taskService.cancel(taskId, principal.id(), principal.superAdmin());
        auditLogService.record(
                principal == null ? null : principal.id(),
                "task.cancel",
                "task",
                taskId,
                Map.of("status", response.status().name(), "type", response.type()),
                request
        );
        return ApiResponse.ok(response, TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/tasks/{taskId}/logs")
    public ApiResponse<PageResponse<TaskLogResponse>> logs(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID taskId,
            @RequestParam(required = false) TaskLogType logType,
            @RequestParam(defaultValue = "1") @Min(1) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(200) int pageSize,
            HttpServletRequest request
    ) {
        projectAccessService.requireTaskAccess(taskId, principal.id(), principal.superAdmin());
        return ApiResponse.ok(taskLogService.list(taskId, logType, page, pageSize), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/tasks/{taskId}/log-increments")
    public ApiResponse<TaskLogIncrementResponse> logIncrements(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID taskId,
            @RequestParam(required = false) String afterEventId,
            @RequestParam(required = false) String limit,
            HttpServletRequest request
    ) {
        projectAccessService.requireTaskAccess(taskId, principal.id(), principal.superAdmin());
        TaskLogIncrementRequest incrementRequest = TaskLogIncrementRequest.from(afterEventId, limit);
        return ApiResponse.ok(taskLogIncrementService.read(taskId, incrementRequest), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/tasks/{taskId}/log-content")
    public ApiResponse<TaskLogContentResponse> logContent(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID taskId,
            @RequestParam(required = false) String types,
            @RequestParam(required = false) Integer lines,
            @RequestParam(required = false) Long mergedOffset,
            @RequestParam(required = false) Long stdoutOffset,
            @RequestParam(required = false) Long stderrOffset,
            @RequestParam(required = false) Integer mergedLines,
            @RequestParam(required = false) Integer stdoutLines,
            @RequestParam(required = false) Integer stderrLines,
            HttpServletRequest request
    ) {
        projectAccessService.requireTaskAccess(taskId, principal.id(), principal.superAdmin());
        TaskLogContentRequest contentRequest = TaskLogContentRequest.from(
                types,
                lines,
                mergedOffset,
                stdoutOffset,
                stderrOffset,
                mergedLines,
                stdoutLines,
                stderrLines
        );
        return ApiResponse.ok(taskLogService.content(taskId, contentRequest), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/tasks/{taskId}/logs/{logId}/download")
    public ResponseEntity<Resource> downloadLog(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID taskId,
            @PathVariable UUID logId
    ) {
        projectAccessService.requireTaskLogAccess(taskId, logId, principal.id(), principal.superAdmin());
        TaskLogService.DownloadableTaskLog log = taskLogService.download(taskId, logId);
        return ResponseEntity.ok()
                .contentType(MediaType.APPLICATION_OCTET_STREAM)
                .header(HttpHeaders.CONTENT_DISPOSITION, ContentDisposition.attachment()
                        .filename(log.filename())
                        .build()
                        .toString())
                .body(log.resource());
    }
}
