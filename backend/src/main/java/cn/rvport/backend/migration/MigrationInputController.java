package cn.rvport.backend.migration;

import cn.rvport.backend.common.web.ApiResponse;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.common.web.TraceIdFilter;
import cn.rvport.backend.security.RvPortUserPrincipal;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import java.util.UUID;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
@Validated
public class MigrationInputController {

    private final MigrationInputService migrationInputService;

    public MigrationInputController(MigrationInputService migrationInputService) {
        this.migrationInputService = migrationInputService;
    }

    @GetMapping("/api/projects/{projectId}/source-revisions/{sourceRevisionId}/migration-inputs")
    public ApiResponse<PageResponse<MigrationInputResponse>> list(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @PathVariable UUID sourceRevisionId,
            @Valid @ModelAttribute MigrationInputListRequest query,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(migrationInputService.list(projectId, sourceRevisionId, query, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request));
    }

    @PostMapping("/api/projects/{projectId}/source-revisions/{sourceRevisionId}/migration-inputs:import")
    public ApiResponse<MigrationInputImportResponse> importRefs(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @PathVariable UUID sourceRevisionId,
            @Valid @RequestBody MigrationInputImportRequest body,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(migrationInputService.importRefs(projectId, sourceRevisionId, body, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request));
    }

    @PostMapping("/api/projects/{projectId}/source-revisions/{sourceRevisionId}/migration-inputs:auto-merge")
    public ApiResponse<MigrationInputAutoMergeResponse> autoMerge(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @PathVariable UUID sourceRevisionId,
            @RequestBody(required = false) MigrationInputAutoMergeRequest body,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(migrationInputService.autoMerge(projectId, sourceRevisionId, body, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/migration-inputs/{migrationInputId}")
    public ApiResponse<MigrationInputDetailResponse> detail(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID migrationInputId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(migrationInputService.detail(migrationInputId, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request));
    }

    @PatchMapping("/api/migration-inputs/{migrationInputId}")
    public ApiResponse<MigrationInputResponse> update(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID migrationInputId,
            @Valid @RequestBody MigrationInputUpdateRequest body,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(migrationInputService.update(migrationInputId, body, principal.id(), principal.superAdmin()),
                TraceIdFilter.currentTraceId(request));
    }
}
