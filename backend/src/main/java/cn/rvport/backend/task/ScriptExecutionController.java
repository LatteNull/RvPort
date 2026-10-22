package cn.rvport.backend.task;

import cn.rvport.backend.common.web.ApiResponse;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.common.web.TraceIdFilter;
import cn.rvport.backend.security.RvPortUserPrincipal;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import java.util.UUID;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class ScriptExecutionController {

    private final ScriptExecutionService scriptExecutionService;

    public ScriptExecutionController(ScriptExecutionService scriptExecutionService) {
        this.scriptExecutionService = scriptExecutionService;
    }

    @GetMapping("/api/projects/{projectId}/script-executions")
    public ApiResponse<PageResponse<ScriptExecutionResponse>> list(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @Valid @ModelAttribute ScriptExecutionListRequest query,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(
                scriptExecutionService.list(projectId, query, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request)
        );
    }

    @GetMapping("/api/script-executions/{executionId}")
    public ApiResponse<ScriptExecutionDetailResponse> get(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID executionId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(
                scriptExecutionService.get(executionId, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request)
        );
    }
}
