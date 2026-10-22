package cn.rvport.backend.kb;

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
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.core.io.Resource;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;

@RestController
@Validated
public class KbScanController {

    private final KbScanService kbScanService;

    public KbScanController(KbScanService kbScanService) {
        this.kbScanService = kbScanService;
    }

    @PostMapping("/api/projects/{projectId}/kb-scans")
    public ApiResponse<TaskResponse> create(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @RequestBody(required = false) KbScanRequest body,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(kbScanService.create(projectId, body, principal.id(), principal.superAdmin(), request), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/projects/{projectId}/kb-scans")
    public ApiResponse<PageResponse<KbScanResponse>> list(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @Valid @ModelAttribute KbScanListRequest query,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(kbScanService.list(projectId, query, principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/projects/{projectId}/kb-scans/latest")
    public ApiResponse<DomainLatestResponse<KbScanResponse>> latest(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(kbScanService.latest(projectId, principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/kb-scans/{scanId}")
    public ApiResponse<KbScanResponse> get(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID scanId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(kbScanService.get(scanId, principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/kb-scans/{scanId}/findings")
    public ApiResponse<PageResponse<FindingResponse>> findings(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID scanId,
            @Valid @ModelAttribute FindingListRequest query,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(kbScanService.findings(scanId, query, principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/kb-scans/{scanId}/artifacts")
    public ApiResponse<PageResponse<KbScanArtifactSummaryResponse>> artifacts(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID scanId,
            @Valid @ModelAttribute KbScanArtifactListRequest query,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(kbScanService.artifacts(scanId, query, principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/kb-scans/{scanId}/artifacts/{artifactId}/download")
    public ResponseEntity<Resource> downloadArtifact(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID scanId,
            @PathVariable UUID artifactId
    ) {
        KbScanService.DownloadableKbScanArtifact artifact = kbScanService.downloadArtifact(scanId, artifactId, principal.id(), principal.superAdmin());
        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType(artifact.contentType()))
                .header(HttpHeaders.CONTENT_DISPOSITION, ContentDisposition.attachment()
                        .filename(artifact.filename())
                        .build()
                .toString())
                .body(artifact.resource());
    }

    @GetMapping("/api/kb-scans/{scanId}/artifacts:download")
    public ResponseEntity<Resource> downloadArtifactByFormat(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID scanId,
            @RequestParam String format
    ) {
        KbScanService.DownloadableKbScanArtifact artifact = kbScanService.downloadArtifactByFormat(scanId, format, principal.id(), principal.superAdmin());
        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType(artifact.contentType()))
                .header(HttpHeaders.CONTENT_DISPOSITION, ContentDisposition.attachment()
                        .filename(artifact.filename())
                        .build()
                        .toString())
                .body(artifact.resource());
    }

    @GetMapping("/api/findings/{findingId}")
    public ApiResponse<FindingResponse> finding(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID findingId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(kbScanService.finding(findingId, principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/findings/{findingId}/code-context")
    public ApiResponse<FindingCodeContextResponse> codeContext(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID findingId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(kbScanService.codeContext(findingId, principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }
}
