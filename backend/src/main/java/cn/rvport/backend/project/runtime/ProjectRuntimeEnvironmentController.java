package cn.rvport.backend.project.runtime;

import cn.rvport.backend.common.web.ApiResponse;
import cn.rvport.backend.common.web.TraceIdFilter;
import cn.rvport.backend.security.RvPortUserPrincipal;
import jakarta.servlet.http.HttpServletRequest;
import java.util.UUID;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
@Validated
public class ProjectRuntimeEnvironmentController {

    private final ProjectRuntimeEnvironmentService service;

    public ProjectRuntimeEnvironmentController(ProjectRuntimeEnvironmentService service) {
        this.service = service;
    }

    @GetMapping("/api/projects/{projectId}/runtime-environments")
    public ApiResponse<ProjectRuntimeEnvironmentResponse> get(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(service.get(projectId, principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @PatchMapping("/api/projects/{projectId}/runtime-environments")
    public ApiResponse<ProjectRuntimeEnvironmentResponse> update(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @RequestBody ProjectRuntimeEnvironmentUpdateRequest body,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(service.update(projectId, body, principal.id(), principal.superAdmin(), request), TraceIdFilter.currentTraceId(request));
    }
}
