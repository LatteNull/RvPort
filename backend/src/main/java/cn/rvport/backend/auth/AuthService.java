package cn.rvport.backend.auth;

import cn.rvport.backend.audit.AuditLogService;
import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.mail.MailConfigService;
import cn.rvport.backend.mail.MailDeliveryService;
import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.user.PasswordPolicy;
import cn.rvport.backend.user.UserRepository;
import cn.rvport.backend.user.UserResponse;
import cn.rvport.backend.user.UserStatus;
import cn.rvport.backend.user.UserView;
import cn.rvport.backend.user.UserWithPassword;
import cn.rvport.backend.useraction.UserActionTokenService;
import cn.rvport.backend.useraction.UserActionTokenType;
import cn.rvport.backend.useraction.UserActionTokenView;
import jakarta.servlet.http.HttpServletRequest;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.context.HttpSessionSecurityContextRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final PasswordPolicy passwordPolicy;
    private final AuditLogService auditLogService;
    private final UserActionTokenService userActionTokenService;
    private final MailDeliveryService mailDeliveryService;
    private final MailConfigService mailConfigService;

    public AuthService(
            UserRepository userRepository,
            PasswordEncoder passwordEncoder,
            PasswordPolicy passwordPolicy,
            AuditLogService auditLogService,
            UserActionTokenService userActionTokenService,
            MailDeliveryService mailDeliveryService,
            MailConfigService mailConfigService
    ) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.passwordPolicy = passwordPolicy;
        this.auditLogService = auditLogService;
        this.userActionTokenService = userActionTokenService;
        this.mailDeliveryService = mailDeliveryService;
        this.mailConfigService = mailConfigService;
    }

    @Transactional
    public LoginResponse login(LoginRequest request, HttpServletRequest httpRequest) {
        UserWithPassword found = userRepository.findByUsernameWithPassword(request.username()).orElse(null);
        if (found == null || !passwordEncoder.matches(request.password(), found.passwordHash())) {
            auditLogService.record(null, "auth.login.failed", "user", null, Map.of("username", request.username()), httpRequest);
            throw new ApiException(HttpStatus.UNAUTHORIZED, "INVALID_CREDENTIALS", "用户名或密码错误");
        }
        if (found.user().status() != UserStatus.ACTIVE) {
            auditLogService.record(found.user().id(), "auth.login.failed", "user", found.user().id(), Map.of("reason", "disabled"), httpRequest);
            throw new ApiException(HttpStatus.FORBIDDEN, "USER_DISABLED", "用户已禁用");
        }

        userRepository.updateLastLoginAt(found.user().id());
        UserView refreshed = userRepository.findById(found.user().id()).orElse(found.user());
        RvPortUserPrincipal principal = RvPortUserPrincipal.from(refreshed);
        UsernamePasswordAuthenticationToken authentication = UsernamePasswordAuthenticationToken.authenticated(
                principal,
                null,
                principal.authorities()
        );
        SecurityContext context = SecurityContextHolder.createEmptyContext();
        context.setAuthentication(authentication);
        SecurityContextHolder.setContext(context);
        httpRequest.getSession(true).setAttribute(
                HttpSessionSecurityContextRepository.SPRING_SECURITY_CONTEXT_KEY,
                context
        );

        auditLogService.record(refreshed.id(), "auth.login.success", "user", refreshed.id(), Map.of("username", refreshed.username()), httpRequest);
        return new LoginResponse(UserResponse.from(refreshed));
    }

    public UserResponse currentUser(RvPortUserPrincipal principal) {
        UserView current = requireActive(principal.id());
        return UserResponse.from(current);
    }

    @Transactional
    public UserResponse changePassword(RvPortUserPrincipal principal, ChangePasswordRequest request, HttpServletRequest httpRequest) {
        UserWithPassword found = userRepository.findByIdWithPassword(principal.id())
                .orElseThrow(() -> new ApiException(HttpStatus.UNAUTHORIZED, "AUTH_REQUIRED", "登录态已失效"));
        if (found.user().status() != UserStatus.ACTIVE) {
            throw new ApiException(HttpStatus.UNAUTHORIZED, "AUTH_REQUIRED", "登录态已失效");
        }
        if (!passwordEncoder.matches(request.currentPassword(), found.passwordHash())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "CURRENT_PASSWORD_INVALID", "当前密码不正确");
        }
        passwordPolicy.validate(found.user().username(), request.newPassword());
        UserView updated = userRepository.changeOwnPassword(found.user().id(), passwordEncoder.encode(request.newPassword()));
        auditLogService.record(updated.id(), "auth.change_password", "user", updated.id(), Map.of("username", updated.username()), httpRequest);
        return UserResponse.from(updated);
    }

    @Transactional
    public UserResponse updateProfile(RvPortUserPrincipal principal, UpdateProfileRequest request, HttpServletRequest httpRequest) {
        if (request.username() != null || request.email() != null || request.superAdmin() != null
                || request.status() != null || request.mustChangePassword() != null || request.passwordHash() != null) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", "请求包含不可写字段");
        }
        UserView current = requireActive(principal.id());
        String displayName = request.displayName() == null ? current.displayName() : blankToNull(request.displayName());
        UserView updated = userRepository.updateProfile(current.id(), displayName);
        auditLogService.record(updated.id(), "auth.profile.update", "user", updated.id(), Map.of("username", updated.username()), httpRequest);
        return UserResponse.from(updated);
    }

    @Transactional
    public UserResponse acceptInvitation(AcceptInvitationRequest request, HttpServletRequest httpRequest) {
        UserActionTokenView token = userActionTokenService.requireOpen(request.token(), UserActionTokenType.INVITATION);
        UserView user = userRepository.findById(token.userId())
                .orElseThrow(() -> new ApiException(HttpStatus.BAD_REQUEST, "ACTION_TOKEN_INVALID", "链接无效或已过期"));
        if (user.status() != UserStatus.ACTIVE) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "ACTION_TOKEN_INVALID", "链接无效或已过期");
        }
        passwordPolicy.validate(user.username(), request.newPassword());
        UserView updated = userRepository.resetPassword(user.id(), passwordEncoder.encode(request.newPassword()), false);
        userActionTokenService.consume(token.id());
        auditLogService.record(updated.id(), "auth.invitation.accept", "user", updated.id(), Map.of("username", updated.username()), httpRequest);
        return UserResponse.from(updated);
    }

    @Transactional
    public void requestPasswordReset(PasswordResetRequest request, HttpServletRequest httpRequest) {
        UserView user = userRepository.findByUsernameOrEmail(request.identifier()).orElse(null);
        if (user == null || user.status() != UserStatus.ACTIVE || user.email() == null || user.email().isBlank()) {
            return;
        }
        UserActionTokenService.IssuedToken issued = userActionTokenService.issuePasswordReset(user.id());
        String url = actionUrl("reset-password", issued.plainToken());
        runAfterCommit(() -> mailDeliveryService.sendPasswordReset(user.email(), url));
        auditLogService.record(user.id(), "auth.password_reset.request", "user", user.id(), Map.of("username", user.username()), httpRequest);
    }

    @Transactional
    public UserResponse confirmPasswordReset(PasswordResetConfirmRequest request, HttpServletRequest httpRequest) {
        UserActionTokenView token = userActionTokenService.requireOpen(request.token(), UserActionTokenType.PASSWORD_RESET);
        UserView user = userRepository.findById(token.userId())
                .orElseThrow(() -> new ApiException(HttpStatus.BAD_REQUEST, "ACTION_TOKEN_INVALID", "链接无效或已过期"));
        if (user.status() != UserStatus.ACTIVE) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "ACTION_TOKEN_INVALID", "链接无效或已过期");
        }
        passwordPolicy.validate(user.username(), request.newPassword());
        UserView updated = userRepository.resetPassword(user.id(), passwordEncoder.encode(request.newPassword()), false);
        userActionTokenService.consume(token.id());
        auditLogService.record(updated.id(), "auth.password_reset.confirm", "user", updated.id(), Map.of("username", updated.username()), httpRequest);
        return UserResponse.from(updated);
    }

    private UserView requireActive(UUID userId) {
        UserView current = userRepository.findById(userId)
                .orElseThrow(() -> new ApiException(HttpStatus.UNAUTHORIZED, "AUTH_REQUIRED", "登录态已失效"));
        if (current.status() != UserStatus.ACTIVE) {
            throw new ApiException(HttpStatus.UNAUTHORIZED, "AUTH_REQUIRED", "登录态已失效");
        }
        return current;
    }

    private String actionUrl(String path, String token) {
        String baseUrl = mailConfigService.currentConfig().frontendBaseUrl();
        if (baseUrl == null || baseUrl.isBlank()) {
            baseUrl = "http://localhost:3000";
        }
        return baseUrl + "/" + path + "?token=" + URLEncoder.encode(token, StandardCharsets.UTF_8);
    }

    private void runAfterCommit(Runnable runnable) {
        if (org.springframework.transaction.support.TransactionSynchronizationManager.isSynchronizationActive()) {
            org.springframework.transaction.support.TransactionSynchronizationManager.registerSynchronization(
                    new org.springframework.transaction.support.TransactionSynchronization() {
                        @Override
                        public void afterCommit() {
                            runnable.run();
                        }
                    }
            );
            return;
        }
        runnable.run();
    }

    private String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }
}
