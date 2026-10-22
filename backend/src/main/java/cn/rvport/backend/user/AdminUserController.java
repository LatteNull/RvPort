package cn.rvport.backend.user;

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
public class AdminUserController {

    private final AdminUserService adminUserService;

    public AdminUserController(AdminUserService adminUserService) {
        this.adminUserService = adminUserService;
    }

    @GetMapping("/api/admin/users")
    public ApiResponse<PageResponse<UserResponse>> list(
            @Valid @ModelAttribute AdminUserListRequest query,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(adminUserService.list(query), TraceIdFilter.currentTraceId(request));
    }

    @PostMapping("/api/admin/users")
    public ApiResponse<UserResponse> create(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @Valid @RequestBody CreateUserRequest body,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(adminUserService.create(body, principal.id(), request), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/admin/users/{userId}")
    public ApiResponse<UserResponse> get(@PathVariable UUID userId, HttpServletRequest request) {
        return ApiResponse.ok(adminUserService.get(userId), TraceIdFilter.currentTraceId(request));
    }

    @PatchMapping("/api/admin/users/{userId}")
    public ApiResponse<UserResponse> update(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID userId,
            @Valid @RequestBody UpdateUserRequest body,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(adminUserService.update(userId, body, principal.id(), request), TraceIdFilter.currentTraceId(request));
    }

    @PostMapping("/api/admin/users/{userId}/reset-password")
    public ApiResponse<UserResponse> resetPassword(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID userId,
            @Valid @RequestBody ResetPasswordRequest body,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(adminUserService.resetPassword(userId, body, principal.id(), request), TraceIdFilter.currentTraceId(request));
    }

    @PostMapping("/api/admin/users/{userId}/send-invitation")
    public ApiResponse<UserResponse> sendInvitation(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID userId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(adminUserService.sendInvitation(userId, principal.id(), request), TraceIdFilter.currentTraceId(request));
    }
}
