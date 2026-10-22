package cn.rvport.backend.environment;

import cn.rvport.backend.common.web.ApiResponse;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.common.web.TraceIdFilter;
import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.task.TaskResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import java.util.UUID;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
@Validated
public class EnvironmentController {

    private final EnvironmentService environmentService;

    public EnvironmentController(EnvironmentService environmentService) {
        this.environmentService = environmentService;
    }

    @GetMapping("/api/projects/{projectId}/environments")
    public ApiResponse<PageResponse<EnvironmentResponse>> list(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @Valid @ModelAttribute EnvironmentListRequest query,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(environmentService.list(projectId, query, principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @PostMapping("/api/projects/{projectId}/environments")
    public ApiResponse<EnvironmentResponse> create(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @Valid @RequestBody CreateEnvironmentRequest body,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(environmentService.create(projectId, body, principal.id(), principal.superAdmin(), request), TraceIdFilter.currentTraceId(request));
    }

    @PostMapping("/api/projects/{projectId}/environments/test-connection")
    public ApiResponse<TaskResponse> precheckConnection(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @Valid @RequestBody EnvironmentPrecheckRequest body,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(environmentService.precheckConnection(projectId, body, principal.id(), principal.superAdmin(), request),
                TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/environments/{environmentId}")
    public ApiResponse<EnvironmentResponse> get(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID environmentId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(environmentService.get(environmentId, principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @PatchMapping("/api/environments/{environmentId}")
    public ApiResponse<EnvironmentResponse> update(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID environmentId,
            @Valid @RequestBody UpdateEnvironmentRequest body,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(environmentService.update(environmentId, body, principal.id(), principal.superAdmin(), request), TraceIdFilter.currentTraceId(request));
    }

    @PostMapping("/api/projects/{projectId}/environments/{environmentId}/test-connection")
    public ApiResponse<TaskResponse> testConnectionInProject(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @PathVariable UUID environmentId,
            @RequestBody(required = false) @Valid EnvironmentRunRequest body,
            HttpServletRequest request
    ) {
        EnvironmentRunRequest safeBody = body == null ? new EnvironmentRunRequest(null) : body;
        return ApiResponse.ok(environmentService.testConnection(projectId, environmentId, safeBody, principal.id(), principal.superAdmin(), request),
                TraceIdFilter.currentTraceId(request));
    }

    @PostMapping("/api/projects/{projectId}/environments/{environmentId}/check")
    public ApiResponse<TaskResponse> check(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @PathVariable UUID environmentId,
            @RequestBody(required = false) @Valid EnvironmentCheckRequest body,
            HttpServletRequest request
    ) {
        EnvironmentCheckRequest safeBody = body == null ? new EnvironmentCheckRequest(null, null, null) : body;
        return ApiResponse.ok(environmentService.check(projectId, environmentId, safeBody, principal.id(), principal.superAdmin(), request),
                TraceIdFilter.currentTraceId(request));
    }

    @PostMapping("/api/projects/{projectId}/environments/{environmentId}/collect")
    public ApiResponse<TaskResponse> collectInProject(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @PathVariable UUID environmentId,
            @RequestBody(required = false) @Valid EnvironmentCollectRequest body,
            HttpServletRequest request
    ) {
        EnvironmentCollectRequest safeBody = body == null ? new EnvironmentCollectRequest(null, null) : body;
        return ApiResponse.ok(environmentService.collect(projectId, environmentId, safeBody, principal.id(), principal.superAdmin(), request),
                TraceIdFilter.currentTraceId(request));
    }

    @PostMapping("/api/projects/{projectId}/environments/{environmentId}/scripts")
    public ApiResponse<TaskResponse> runScriptInProject(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @PathVariable UUID environmentId,
            @Valid @RequestBody RunScriptRequest body,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(environmentService.runScript(projectId, environmentId, body, principal.id(), principal.superAdmin(), request),
                TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/environments/{environmentId}/snapshots")
    public ApiResponse<PageResponse<EnvironmentSnapshotResponse>> snapshots(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID environmentId,
            @Valid @ModelAttribute SnapshotListRequest query,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(environmentService.snapshots(environmentId, query, principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }
}
