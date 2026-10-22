package cn.rvport.backend.kb.ai;

import cn.rvport.backend.common.web.ApiResponse;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.common.web.TraceIdFilter;
import cn.rvport.backend.security.RvPortUserPrincipal;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import java.util.List;
import java.util.UUID;
import org.springframework.core.io.Resource;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
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
public class KbAiExtensionController {

    private final KbAiExtensionService service;

    public KbAiExtensionController(KbAiExtensionService service) {
        this.service = service;
    }

    @PostMapping("/api/projects/{projectId}/kb-scans/{scanId}/ai-extensions")
    public ApiResponse<KbAiExtensionCreateResponse> create(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @PathVariable UUID scanId,
            @RequestBody(required = false) KbAiExtensionRequest body,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(service.create(projectId, scanId, body, principal.id(), principal.superAdmin(), request),
                TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/projects/{projectId}/kb-ai-extensions")
    public ApiResponse<PageResponse<KbAiExtensionResponse>> list(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @Valid @ModelAttribute KbAiExtensionListRequest query,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(service.list(projectId, query, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/projects/{projectId}/kb-scans/{scanId}/ai-extension-readiness")
    public ApiResponse<KbAiExtensionReadinessResponse> readiness(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @PathVariable UUID scanId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(service.readiness(projectId, scanId, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/kb-ai-extensions/{runId}")
    public ApiResponse<KbAiExtensionResponse> get(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID runId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(service.get(runId, principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/kb-ai-extensions/{runId}/artifacts")
    public ApiResponse<List<KbAiExtensionArtifactResponse>> artifacts(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID runId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(service.artifacts(runId, principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/kb-ai-extensions/{runId}/artifacts/{artifactId}/download")
    public ResponseEntity<Resource> downloadArtifact(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID runId,
            @PathVariable UUID artifactId
    ) {
        KbAiExtensionService.DownloadableArtifact artifact = service.downloadArtifact(runId, artifactId, principal.id(), principal.superAdmin());
        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType(artifact.contentType()))
                .header(HttpHeaders.CONTENT_DISPOSITION, ContentDisposition.attachment().filename(artifact.filename()).build().toString())
                .body(artifact.resource());
    }
}
