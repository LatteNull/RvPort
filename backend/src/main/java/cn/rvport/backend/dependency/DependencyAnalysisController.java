package cn.rvport.backend.dependency;

import cn.rvport.backend.common.web.ApiResponse;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.common.web.TraceIdFilter;
import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.workflow.DomainLatestResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import java.util.List;
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
public class DependencyAnalysisController {

    private final DependencyAnalysisService service;

    public DependencyAnalysisController(DependencyAnalysisService service) {
        this.service = service;
    }

    @PostMapping("/api/projects/{projectId}/dependency-analyses")
    public ApiResponse<DependencyAnalysisCreateResponse> create(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @RequestBody(required = false) DependencyAnalysisCreateRequest body,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(service.create(projectId, body, principal.id(), principal.superAdmin(), request),
                TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/projects/{projectId}/dependency-analyses")
    public ApiResponse<PageResponse<DependencyAnalysisResponse>> list(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @Valid @ModelAttribute DependencyAnalysisListRequest query,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(service.list(projectId, query, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/projects/{projectId}/dependency-analyses/latest")
    public ApiResponse<DomainLatestResponse<DependencyAnalysisResponse>> latest(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(service.latest(projectId, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/dependency-analyses/{analysisId}")
    public ApiResponse<DependencyAnalysisResponse> get(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID analysisId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(service.get(analysisId, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/dependency-analyses/{analysisId}/results")
    public ApiResponse<PageResponse<DependencyAnalysisResultItemResponse>> results(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID analysisId,
            @Valid @ModelAttribute DependencyAnalysisResultListRequest query,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(service.results(analysisId, query, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/dependency-analysis-results/{resultItemId}")
    public ApiResponse<DependencyAnalysisResultItemResponse> result(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID resultItemId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(service.result(resultItemId, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/dependency-analyses/{analysisId}/artifacts")
    public ApiResponse<List<DependencyAnalysisArtifactResponse>> artifacts(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID analysisId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(service.artifacts(analysisId, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/dependency-analyses/{analysisId}/artifacts/{artifactType}")
    public ApiResponse<DependencyAnalysisArtifactDetailResponse> artifact(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID analysisId,
            @PathVariable String artifactType,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(service.artifact(analysisId, artifactType, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request));
    }
}
