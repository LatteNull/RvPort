package cn.rvport.backend.buildvalidation;

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
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@Validated
public class BuildValidationController {

    private final BuildValidationService buildValidationService;

    public BuildValidationController(BuildValidationService buildValidationService) {
        this.buildValidationService = buildValidationService;
    }

    @PostMapping("/api/projects/{projectId}/builds")
    public ApiResponse<BuildValidationCreateResponse> create(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @Valid @RequestBody BuildValidationCreateRequest body,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(
                buildValidationService.create(projectId, body, principal.id(), principal.superAdmin(), request),
                TraceIdFilter.currentTraceId(request)
        );
    }

    @GetMapping("/api/projects/{projectId}/builds")
    public ApiResponse<PageResponse<BuildValidationResponse>> list(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @Valid @ModelAttribute BuildValidationListRequest query,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(
                buildValidationService.list(projectId, query, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request)
        );
    }

    @GetMapping("/api/projects/{projectId}/builds/latest")
    public ApiResponse<DomainLatestResponse<BuildValidationResponse>> latest(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @RequestParam(defaultValue = "VALIDATION") BuildValidationLatestMode mode,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(
                buildValidationService.latest(projectId, mode, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request)
        );
    }

    @GetMapping("/api/builds/{buildId}")
    public ApiResponse<BuildValidationResponse> get(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID buildId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(
                buildValidationService.get(buildId, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request)
        );
    }

    @PostMapping("/api/builds/{buildId}/cancel")
    public ApiResponse<TaskResponse> cancel(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID buildId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(
                buildValidationService.cancel(buildId, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request)
        );
    }
}
