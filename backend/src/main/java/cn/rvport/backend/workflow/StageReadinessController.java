package cn.rvport.backend.workflow;

import cn.rvport.backend.common.web.ApiResponse;
import cn.rvport.backend.common.web.TraceIdFilter;
import cn.rvport.backend.security.RvPortUserPrincipal;
import jakarta.servlet.http.HttpServletRequest;
import java.util.UUID;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class StageReadinessController {

    private final StageReadinessService readinessService;

    public StageReadinessController(StageReadinessService readinessService) {
        this.readinessService = readinessService;
    }

    @GetMapping("/api/projects/{projectId}/readiness")
    public ApiResponse<StageReadinessResponse> readiness(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @RequestParam String stageId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(
                readinessService.readiness(projectId, stageId, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request)
        );
    }
}
