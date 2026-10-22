package cn.rvport.backend.source;

import cn.rvport.backend.common.web.ApiResponse;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.common.web.TraceIdFilter;
import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.task.TaskResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import java.util.UUID;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

@RestController
@Validated
public class SourceController {

    private final SourceService sourceService;
    private final SourceCompareService sourceCompareService;

    public SourceController(SourceService sourceService, SourceCompareService sourceCompareService) {
        this.sourceService = sourceService;
        this.sourceCompareService = sourceCompareService;
    }

    @GetMapping("/api/projects/{projectId}/sources")
    public ApiResponse<PageResponse<SourceRevisionResponse>> list(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @Valid @ModelAttribute SourceListRequest query,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(sourceService.list(projectId, query, principal.id(), principal.superAdmin()), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/projects/{projectId}/source/compare/latest")
    public ApiResponse<LatestSourceCompareResponse> latestCompare(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(
                sourceCompareService.latest(projectId, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request)
        );
    }

    @PostMapping("/api/projects/{projectId}/rechecks")
    public ApiResponse<TaskResponse> createRecheck(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @Valid @RequestBody RecheckCreateRequest body,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(
                sourceCompareService.create(projectId, body, principal.id(), principal.superAdmin(), request),
                TraceIdFilter.currentTraceId(request)
        );
    }

    @PostMapping("/api/projects/{projectId}/rechecks/latest")
    public ApiResponse<TaskResponse> createLatestRecheck(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(
                sourceCompareService.createLatest(projectId, principal.id(), principal.superAdmin(), request),
                TraceIdFilter.currentTraceId(request)
        );
    }

    @GetMapping("/api/rechecks/{recheckRunId}/diff-items")
    public ApiResponse<PageResponse<RecheckDiffItemResponse>> diffItems(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID recheckRunId,
            @Valid @ModelAttribute RecheckDiffItemListRequest query,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(
                sourceCompareService.diffItems(recheckRunId, query, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request)
        );
    }

    @GetMapping("/api/rechecks/{recheckRunId}/diff-items/{diffItemId}")
    public ApiResponse<RecheckDiffItemDetailResponse> diffItem(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID recheckRunId,
            @PathVariable UUID diffItemId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(
                sourceCompareService.diffItem(recheckRunId, diffItemId, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request)
        );
    }

    @PostMapping("/api/projects/{projectId}/sources/archive")
    public ApiResponse<SourceArchiveResponse> uploadArchive(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @RequestPart("file") MultipartFile file,
            @RequestParam(required = false) String versionLabel,
            @RequestParam(required = false) String versionNote,
            @RequestParam(defaultValue = "true") boolean activate,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(
                sourceService.uploadArchive(projectId, file, versionLabel, versionNote, activate, principal.id(), principal.superAdmin(), request),
                TraceIdFilter.currentTraceId(request)
        );
    }

    @PostMapping("/api/projects/{projectId}/sources/git-sync")
    public ApiResponse<TaskResponse> gitSync(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @Valid @RequestBody GitSyncRequest body,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(sourceService.gitSync(projectId, body, principal.id(), principal.superAdmin(), request), TraceIdFilter.currentTraceId(request));
    }

    @PostMapping("/api/projects/{projectId}/sources/{sourceRevisionId}/activate")
    public ApiResponse<SourceRevisionResponse> activate(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @PathVariable UUID sourceRevisionId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(
                sourceService.activate(projectId, sourceRevisionId, principal.id(), principal.superAdmin(), request),
                TraceIdFilter.currentTraceId(request)
        );
    }
}
