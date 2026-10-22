package cn.rvport.backend.analysis;

import cn.rvport.backend.artifact.StoredArtifactResource;
import cn.rvport.backend.common.web.ApiResponse;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.common.web.TraceIdFilter;
import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.task.TaskResponse;
import cn.rvport.backend.workflow.DomainLatestResponse;
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
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class SpecializedAnalysisController {

    private final SpecializedAnalysisService service;

    public SpecializedAnalysisController(SpecializedAnalysisService service) {
        this.service = service;
    }

    @PostMapping("/api/projects/{projectId}/floating-point-analyses")
    public ApiResponse<TaskResponse> createFloating(@AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId, HttpServletRequest request) {
        return ApiResponse.ok(service.create(projectId, SpecializedAnalyzerType.FLOATING_POINT,
                principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @PostMapping("/api/projects/{projectId}/memory-order-analyses")
    public ApiResponse<TaskResponse> createMemory(@AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId, HttpServletRequest request) {
        return ApiResponse.ok(service.create(projectId, SpecializedAnalyzerType.MEMORY_ORDER,
                principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/projects/{projectId}/floating-point-analyses")
    public ApiResponse<PageResponse<SpecializedAnalysisResponse>> listFloating(
            @AuthenticationPrincipal RvPortUserPrincipal principal, @PathVariable UUID projectId,
            @Valid @ModelAttribute SpecializedAnalysisListRequest query, HttpServletRequest request) {
        return ApiResponse.ok(service.list(projectId, SpecializedAnalyzerType.FLOATING_POINT, query,
                principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/projects/{projectId}/memory-order-analyses")
    public ApiResponse<PageResponse<SpecializedAnalysisResponse>> listMemory(
            @AuthenticationPrincipal RvPortUserPrincipal principal, @PathVariable UUID projectId,
            @Valid @ModelAttribute SpecializedAnalysisListRequest query, HttpServletRequest request) {
        return ApiResponse.ok(service.list(projectId, SpecializedAnalyzerType.MEMORY_ORDER, query,
                principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/projects/{projectId}/floating-point-analyses/latest")
    public ApiResponse<DomainLatestResponse<SpecializedAnalysisResponse>> latestFloating(
            @AuthenticationPrincipal RvPortUserPrincipal principal, @PathVariable UUID projectId,
            HttpServletRequest request) {
        return ApiResponse.ok(service.latest(projectId, SpecializedAnalyzerType.FLOATING_POINT,
                principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/projects/{projectId}/memory-order-analyses/latest")
    public ApiResponse<DomainLatestResponse<SpecializedAnalysisResponse>> latestMemory(
            @AuthenticationPrincipal RvPortUserPrincipal principal, @PathVariable UUID projectId,
            HttpServletRequest request) {
        return ApiResponse.ok(service.latest(projectId, SpecializedAnalyzerType.MEMORY_ORDER,
                principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/projects/{projectId}/floating-point-analyses/{runId}")
    public ApiResponse<SpecializedAnalysisResponse> floating(
            @AuthenticationPrincipal RvPortUserPrincipal principal, @PathVariable UUID projectId,
            @PathVariable UUID runId, HttpServletRequest request) {
        return ApiResponse.ok(service.get(projectId, SpecializedAnalyzerType.FLOATING_POINT, runId,
                principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/projects/{projectId}/memory-order-analyses/{runId}")
    public ApiResponse<SpecializedAnalysisResponse> memory(
            @AuthenticationPrincipal RvPortUserPrincipal principal, @PathVariable UUID projectId,
            @PathVariable UUID runId, HttpServletRequest request) {
        return ApiResponse.ok(service.get(projectId, SpecializedAnalyzerType.MEMORY_ORDER, runId,
                principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/projects/{projectId}/floating-point-analyses/{runId}/findings")
    public ApiResponse<PageResponse<SpecializedFindingResponse>> floatingFindings(
            @AuthenticationPrincipal RvPortUserPrincipal principal, @PathVariable UUID projectId,
            @PathVariable UUID runId, @Valid @ModelAttribute SpecializedFindingListRequest query,
            HttpServletRequest request) {
        return ApiResponse.ok(service.findings(projectId, SpecializedAnalyzerType.FLOATING_POINT, runId, query,
                principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/projects/{projectId}/memory-order-analyses/{runId}/findings")
    public ApiResponse<PageResponse<SpecializedFindingResponse>> memoryFindings(
            @AuthenticationPrincipal RvPortUserPrincipal principal, @PathVariable UUID projectId,
            @PathVariable UUID runId, @Valid @ModelAttribute SpecializedFindingListRequest query,
            HttpServletRequest request) {
        return ApiResponse.ok(service.findings(projectId, SpecializedAnalyzerType.MEMORY_ORDER, runId, query,
                principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/projects/{projectId}/floating-point-findings/{findingId}")
    public ApiResponse<SpecializedFindingResponse> floatingFinding(
            @AuthenticationPrincipal RvPortUserPrincipal principal, @PathVariable UUID projectId,
            @PathVariable UUID findingId, HttpServletRequest request) {
        return ApiResponse.ok(service.finding(projectId, SpecializedAnalyzerType.FLOATING_POINT, findingId,
                principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/projects/{projectId}/memory-order-findings/{findingId}")
    public ApiResponse<SpecializedFindingResponse> memoryFinding(
            @AuthenticationPrincipal RvPortUserPrincipal principal, @PathVariable UUID projectId,
            @PathVariable UUID findingId, HttpServletRequest request) {
        return ApiResponse.ok(service.finding(projectId, SpecializedAnalyzerType.MEMORY_ORDER, findingId,
                principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/projects/{projectId}/floating-point-analyses/{runId}/artifacts:download")
    public ResponseEntity<Resource> floatingArtifact(@AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId, @PathVariable UUID runId, @RequestParam String format) {
        return artifact(service.download(projectId, SpecializedAnalyzerType.FLOATING_POINT, runId, format,
                principal.id(), principal.superAdmin()), "floating-point-" + runId + "." + extension(format));
    }

    @GetMapping("/api/projects/{projectId}/memory-order-analyses/{runId}/artifacts:download")
    public ResponseEntity<Resource> memoryArtifact(@AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId, @PathVariable UUID runId, @RequestParam String format) {
        return artifact(service.download(projectId, SpecializedAnalyzerType.MEMORY_ORDER, runId, format,
                principal.id(), principal.superAdmin()), "memory-order-" + runId + "." + extension(format));
    }

    private ResponseEntity<Resource> artifact(StoredArtifactResource artifact, String filename) {
        return ResponseEntity.ok().contentType(MediaType.parseMediaType(artifact.artifact().contentType()))
                .header(HttpHeaders.CONTENT_DISPOSITION, ContentDisposition.attachment().filename(filename).build().toString())
                .body(artifact.resource());
    }

    private static String extension(String format) { return "audit".equalsIgnoreCase(format) ? "tgz" : format.toLowerCase(); }
}
