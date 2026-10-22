package cn.rvport.backend.testcomparison;

import cn.rvport.backend.common.web.ApiResponse;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.common.web.TraceIdFilter;
import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.task.TaskResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import java.util.UUID;
import org.springframework.core.io.Resource;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class TestComparisonController {

    private final TestComparisonService service;

    public TestComparisonController(TestComparisonService service) {
        this.service = service;
    }

    @GetMapping("/api/projects/{projectId}/test-comparisons")
    public ApiResponse<PageResponse<TestComparisonResponse>> list(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @Valid @ModelAttribute TestComparisonListRequest query,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(service.list(projectId, query, principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/test-comparisons/{comparisonId}")
    public ApiResponse<TestComparisonResponse> get(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID comparisonId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(service.get(comparisonId, principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/test-comparisons/{comparisonId}/findings")
    public ApiResponse<PageResponse<TestComparisonFindingResponse>> findings(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID comparisonId,
            @Valid @ModelAttribute TestComparisonFindingListRequest query,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(service.findings(comparisonId, query, principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @PostMapping("/api/test-comparisons/{comparisonId}/cancel")
    public ApiResponse<TaskResponse> cancel(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID comparisonId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(service.cancel(comparisonId, principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/test-comparisons/{comparisonId}/agent-output")
    public ResponseEntity<Resource> downloadAgentOutput(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID comparisonId
    ) {
        TestComparisonService.AgentOutputDownload download = service.downloadAgentOutput(comparisonId, principal.id(), principal.superAdmin());
        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType(download.contentType()))
                .header(HttpHeaders.CONTENT_DISPOSITION, ContentDisposition.attachment().filename(download.filename()).build().toString())
                .body(download.resource());
    }
}
