package cn.rvport.backend.optimization;

import cn.rvport.backend.common.web.ApiResponse;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.common.web.TraceIdFilter;
import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.workflow.DomainLatestResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import java.util.UUID;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

@RestController
@Validated
public class OptimizationCycleController {

    private final OptimizationCycleService optimizationCycleService;

    public OptimizationCycleController(OptimizationCycleService optimizationCycleService) {
        this.optimizationCycleService = optimizationCycleService;
    }

    @GetMapping("/api/projects/{projectId}/optimization/overview")
    public ApiResponse<OptimizationOverviewResponse> overview(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(
                optimizationCycleService.overview(projectId, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request)
        );
    }

    @GetMapping("/api/projects/{projectId}/optimization/cycles")
    public ApiResponse<PageResponse<OptimizationCycleResponse>> list(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @Valid @ModelAttribute OptimizationCycleListRequest query,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(
                optimizationCycleService.list(projectId, query, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request)
        );
    }

    @GetMapping("/api/projects/{projectId}/optimization-cycles/latest")
    public ApiResponse<DomainLatestResponse<OptimizationCycleResponse>> latest(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(
                optimizationCycleService.latest(projectId, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request)
        );
    }

    @GetMapping("/api/projects/{projectId}/optimization/cycles/{cycleId}")
    public ApiResponse<OptimizationCycleResponse> get(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @PathVariable UUID cycleId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(
                optimizationCycleService.get(projectId, cycleId, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request)
        );
    }
}
