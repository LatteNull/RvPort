package cn.rvport.backend.archive;

import cn.rvport.backend.common.web.ApiResponse;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.common.web.TraceIdFilter;
import cn.rvport.backend.security.RvPortUserPrincipal;
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
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@Validated
public class ProjectArchiveController {

    private final ProjectArchiveService archiveService;

    public ProjectArchiveController(ProjectArchiveService archiveService) {
        this.archiveService = archiveService;
    }

    @PostMapping("/api/projects/{projectId}/archives")
    public ApiResponse<ProjectArchiveCreateResponse> create(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(
                archiveService.createCurrent(projectId, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request)
        );
    }

    @GetMapping("/api/projects/{projectId}/archives/overview")
    public ApiResponse<ProjectArchiveOverviewResponse> overview(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(
                archiveService.overview(projectId, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request)
        );
    }

    @GetMapping("/api/projects/{projectId}/archives/latest")
    public ApiResponse<DomainLatestResponse<ProjectArchiveResponse>> latest(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(
                archiveService.latest(projectId, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request)
        );
    }

    @GetMapping("/api/projects/{projectId}/archives")
    public ApiResponse<PageResponse<ProjectArchiveResponse>> list(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @Valid @ModelAttribute ProjectArchiveListRequest query,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(
                archiveService.list(projectId, query, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request)
        );
    }

    @GetMapping("/api/archives/{archiveId}")
    public ApiResponse<ProjectArchiveResponse> get(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID archiveId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(
                archiveService.get(archiveId, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request)
        );
    }

    @GetMapping("/api/archives/{archiveId}/items/{itemId}")
    public ResponseEntity<Resource> item(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID archiveId,
            @PathVariable UUID itemId,
            @RequestParam String format
    ) {
        ProjectArchiveDownload download = archiveService.downloadItem(archiveId, itemId, format, principal.id(), principal.superAdmin());
        return downloadable(download);
    }

    @GetMapping("/api/archives/{archiveId}/download")
    public ResponseEntity<Resource> download(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID archiveId
    ) {
        return downloadable(archiveService.download(archiveId, principal.id(), principal.superAdmin()));
    }

    private ResponseEntity<Resource> downloadable(ProjectArchiveDownload download) {
        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType(download.contentType()))
                .header(HttpHeaders.CONTENT_DISPOSITION, ContentDisposition.attachment()
                        .filename(download.filename())
                        .build()
                        .toString())
                .body(download.resource());
    }
}
