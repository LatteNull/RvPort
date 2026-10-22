package cn.rvport.backend.dependency.autofix;

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
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
@Validated
public class DependencyAutoFixController {

    private final DependencyAutoFixService service;

    public DependencyAutoFixController(DependencyAutoFixService service) {
        this.service = service;
    }

    @GetMapping("/api/dependency-analyses/{analysisId}/auto-fix-candidates")
    public ApiResponse<PageResponse<DependencyAutoFixCandidateResponse>> candidates(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID analysisId,
            @Valid @ModelAttribute DependencyAutoFixCandidateListRequest query,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(service.candidates(analysisId, query, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request));
    }

    @PostMapping("/api/dependency-analyses/{analysisId}/auto-fixes")
    public ApiResponse<DependencyAutoFixCreateResponse> create(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID analysisId,
            @Valid @RequestBody DependencyAutoFixCreateRequest body,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(service.create(analysisId, body, principal.id(), principal.superAdmin(), request),
                TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/dependency-auto-fixes/{autoFixRunId}")
    public ApiResponse<DependencyAutoFixRunResponse> get(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID autoFixRunId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(service.get(autoFixRunId, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/dependency-auto-fixes/{autoFixRunId}/items")
    public ApiResponse<PageResponse<DependencyAutoFixItemResponse>> items(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID autoFixRunId,
            @Valid @ModelAttribute DependencyAutoFixItemListRequest query,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(service.items(autoFixRunId, query, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/projects/{projectId}/dependency-auto-fixes")
    public ApiResponse<PageResponse<DependencyAutoFixRunResponse>> list(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @Valid @ModelAttribute DependencyAutoFixRunListRequest query,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(service.list(projectId, query, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request));
    }
}
