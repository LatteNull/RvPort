package cn.rvport.backend.automatedtest;

import cn.rvport.backend.common.web.ApiResponse;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.common.web.TraceIdFilter;
import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.task.TaskResponse;
import cn.rvport.backend.workflow.DomainLatestResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import java.util.UUID;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class AutomatedTestController {

    private final AutomatedTestService service;

    public AutomatedTestController(AutomatedTestService service) {
        this.service = service;
    }

    @PostMapping("/api/projects/{projectId}/tests")
    public ApiResponse<TaskResponse> create(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @Valid @RequestBody AutomatedTestRequest body,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(service.create(projectId, body, principal.id(), principal.superAdmin(), request), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/projects/{projectId}/tests")
    public ApiResponse<PageResponse<AutomatedTestResponse>> list(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @Valid @ModelAttribute AutomatedTestListRequest query,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(service.list(projectId, query, principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/projects/{projectId}/automated-tests/latest")
    public ApiResponse<DomainLatestResponse<AutomatedTestResponse>> latest(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(service.latest(projectId, principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/tests/{testRunId}")
    public ApiResponse<AutomatedTestResponse> get(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID testRunId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(service.get(testRunId, principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @PostMapping("/api/tests/{testRunId}/cancel")
    public ApiResponse<TaskResponse> cancel(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID testRunId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(service.cancel(testRunId, principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }
}
