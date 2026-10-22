package cn.rvport.backend.project;

import cn.rvport.backend.common.web.ApiResponse;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.common.web.TraceIdFilter;
import cn.rvport.backend.security.RvPortUserPrincipal;
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
public class ProjectController {

    private final ProjectService projectService;

    public ProjectController(ProjectService projectService) {
        this.projectService = projectService;
    }

    @GetMapping("/api/projects")
    public ApiResponse<PageResponse<ProjectResponse>> list(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @Valid @ModelAttribute ProjectListRequest query,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(projectService.list(query, principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @PostMapping("/api/projects")
    public ApiResponse<ProjectResponse> create(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @Valid @RequestBody CreateProjectRequest body,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(projectService.create(body, principal.id(), request), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/projects/{projectId}")
    public ApiResponse<ProjectResponse> get(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(projectService.get(projectId, principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @PatchMapping("/api/projects/{projectId}")
    public ApiResponse<ProjectResponse> update(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @Valid @RequestBody UpdateProjectRequest body,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(projectService.update(projectId, body, principal.id(), principal.superAdmin(), request), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/projects/{projectId}/overview")
    public ApiResponse<ProjectOverviewResponse> overview(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(projectService.overview(projectId, principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }
}
