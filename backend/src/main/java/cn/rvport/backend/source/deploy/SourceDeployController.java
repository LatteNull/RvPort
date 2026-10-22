package cn.rvport.backend.source.deploy;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.common.web.ApiResponse;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.common.web.TraceIdFilter;
import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.task.TaskResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import java.util.UUID;
import org.springframework.http.HttpStatus;
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
public class SourceDeployController {

    private final SourceDeployService sourceDeployService;

    public SourceDeployController(SourceDeployService sourceDeployService) {
        this.sourceDeployService = sourceDeployService;
    }

    @PostMapping("/api/projects/{projectId}/source-deployments")
    public ApiResponse<SourceDeployCreateResponse> create(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @Valid @RequestBody SourceDeployCreateRequest body,
            HttpServletRequest request
    ) {
        throw new ApiException(
                HttpStatus.GONE,
                "SOURCE_DEPLOYMENT_CREATE_DEPRECATED",
                "源码部署已内置到构建验证任务中，不能通过正式 API 单独创建"
        );
    }

    @GetMapping("/api/projects/{projectId}/source-deployments")
    public ApiResponse<PageResponse<SourceDeployResponse>> list(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @Valid @ModelAttribute SourceDeployListRequest query,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(
                sourceDeployService.list(projectId, query, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request)
        );
    }

    @GetMapping("/api/source-deployments/{sourceDeploymentId}")
    public ApiResponse<SourceDeployResponse> get(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID sourceDeploymentId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(
                sourceDeployService.get(sourceDeploymentId, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request)
        );
    }

    @PostMapping("/api/source-deployments/{sourceDeploymentId}/cancel")
    public ApiResponse<TaskResponse> cancel(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID sourceDeploymentId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(
                sourceDeployService.cancel(sourceDeploymentId, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request)
        );
    }
}
