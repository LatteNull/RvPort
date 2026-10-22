package cn.rvport.backend.auth;

import cn.rvport.backend.audit.AuditLogService;
import cn.rvport.backend.common.web.ApiResponse;
import cn.rvport.backend.common.web.TraceIdFilter;
import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.user.UserResponse;
import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;
import jakarta.validation.Valid;
import java.util.Map;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.csrf.CsrfToken;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class AuthController {

    private final AuthService authService;
    private final AuditLogService auditLogService;

    public AuthController(AuthService authService, AuditLogService auditLogService) {
        this.authService = authService;
        this.auditLogService = auditLogService;
    }

    @GetMapping("/api/auth/csrf")
    public ApiResponse<CsrfTokenResponse> csrf(CsrfToken csrfToken, HttpServletRequest request) {
        return ApiResponse.ok(
                new CsrfTokenResponse(csrfToken.getHeaderName(), csrfToken.getParameterName(), csrfToken.getToken()),
                TraceIdFilter.currentTraceId(request)
        );
    }

    @PostMapping("/api/auth/login")
    public ApiResponse<LoginResponse> login(@Valid @RequestBody LoginRequest body, HttpServletRequest request) {
        return ApiResponse.ok(authService.login(body, request), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/auth/me")
    public ApiResponse<UserResponse> me(@AuthenticationPrincipal RvPortUserPrincipal principal, HttpServletRequest request) {
        return ApiResponse.ok(authService.currentUser(principal), TraceIdFilter.currentTraceId(request));
    }

    @PostMapping("/api/auth/change-password")
    public ApiResponse<UserResponse> changePassword(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @Valid @RequestBody ChangePasswordRequest body,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(authService.changePassword(principal, body, request), TraceIdFilter.currentTraceId(request));
    }

    @PatchMapping("/api/auth/profile")
    public ApiResponse<UserResponse> updateProfile(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @Valid @RequestBody UpdateProfileRequest body,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(authService.updateProfile(principal, body, request), TraceIdFilter.currentTraceId(request));
    }

    @PostMapping("/api/auth/invitations/accept")
    public ApiResponse<UserResponse> acceptInvitation(
            @Valid @RequestBody AcceptInvitationRequest body,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(authService.acceptInvitation(body, request), TraceIdFilter.currentTraceId(request));
    }

    @PostMapping("/api/auth/password-resets/request")
    public ApiResponse<Map<String, Boolean>> requestPasswordReset(
            @Valid @RequestBody PasswordResetRequest body,
            HttpServletRequest request
    ) {
        authService.requestPasswordReset(body, request);
        return ApiResponse.ok(Map.of("accepted", true), TraceIdFilter.currentTraceId(request));
    }

    @PostMapping("/api/auth/password-resets/confirm")
    public ApiResponse<UserResponse> confirmPasswordReset(
            @Valid @RequestBody PasswordResetConfirmRequest body,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(authService.confirmPasswordReset(body, request), TraceIdFilter.currentTraceId(request));
    }

    @PostMapping("/api/auth/logout")
    public ApiResponse<Map<String, Boolean>> logout(
            HttpServletRequest request,
            HttpServletResponse response
    ) {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        RvPortUserPrincipal principal = authentication != null && authentication.getPrincipal() instanceof RvPortUserPrincipal current
                ? current
                : null;
        if (principal != null) {
            auditLogService.record(principal.id(), "auth.logout", "user", principal.id(), Map.of("username", principal.username()), request);
        }
        SecurityContextHolder.clearContext();
        HttpSession session = request.getSession(false);
        if (session != null) {
            session.invalidate();
        }
        Cookie cookie = new Cookie("RVPORT_SESSION", "");
        cookie.setPath("/");
        cookie.setHttpOnly(true);
        cookie.setMaxAge(0);
        response.addCookie(cookie);
        return ApiResponse.ok(Map.of("loggedOut", true), TraceIdFilter.currentTraceId(request));
    }

}
