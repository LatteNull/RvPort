package cn.rvport.backend.user;

import cn.rvport.backend.audit.AuditLogService;
import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.mail.MailConfigService;
import cn.rvport.backend.mail.MailDeliveryService;
import cn.rvport.backend.useraction.UserActionTokenService;
import jakarta.servlet.http.HttpServletRequest;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AdminUserService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final PasswordPolicy passwordPolicy;
    private final AuditLogService auditLogService;
    private final UserActionTokenService userActionTokenService;
    private final MailDeliveryService mailDeliveryService;
    private final MailConfigService mailConfigService;

    public AdminUserService(
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

    public PageResponse<UserResponse> list(AdminUserListRequest request) {
        int page = request.normalizedPage();
        int pageSize = request.normalizedPageSize();
        long total = userRepository.count(request.status(), request.keyword());
        List<UserResponse> items = userRepository.list(request.status(), request.keyword(), page, pageSize).stream()
                .map(UserResponse::from)
                .toList();
        return PageResponse.of(items, page, pageSize, total);
    }

    @Transactional
    public UserResponse create(CreateUserRequest request, UUID actorUserId, HttpServletRequest httpRequest) {
        rejectCreateForbiddenFields(request);
        String username = request.username().trim();
        String email = blankToNull(request.email());
        if (email == null) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "EMAIL_REQUIRED", "邮箱不能为空");
        }
        if (userRepository.existsByUsername(username)) {
            throw new ApiException(HttpStatus.CONFLICT, "USERNAME_EXISTS", "用户名已存在");
        }
        if (userRepository.existsByEmail(email)) {
            throw new ApiException(HttpStatus.CONFLICT, "EMAIL_EXISTS", "邮箱已存在");
        }
        UserView user = userRepository.create(
                username,
                blankToNull(request.displayName()),
                email,
                passwordEncoder.encode(UUID.randomUUID().toString() + UUID.randomUUID()),
                request.mustChangePassword() == null || request.mustChangePassword(),
                request.status() == null ? UserStatus.ACTIVE : request.status()
        );
        UserActionTokenService.IssuedToken token = userActionTokenService.issueInvitation(user.id(), actorUserId);
        runAfterCommit(() -> mailDeliveryService.sendInvitation(user.email(), user.username(), invitationUrl(token.plainToken())));
        auditLogService.record(actorUserId, "admin.user.create", "user", user.id(), Map.of("username", user.username()), httpRequest);
        return UserResponse.from(user);
    }

    public UserResponse get(UUID userId) {
        return UserResponse.from(requireUser(userId));
    }

    @Transactional
    public UserResponse update(UUID userId, UpdateUserRequest request, UUID actorUserId, HttpServletRequest httpRequest) {
        rejectUpdateForbiddenFields(request);
        UserView current = requireUser(userId);
        String email = request.email() == null ? current.email() : blankToNull(request.email());
        if (email != null && userRepository.existsByEmailExcludingId(email, userId)) {
            throw new ApiException(HttpStatus.CONFLICT, "EMAIL_EXISTS", "邮箱已存在");
        }

        String displayName = request.displayName() == null ? current.displayName() : blankToNull(request.displayName());
        UserStatus status = request.status() == null ? current.status() : request.status();
        List<String> changedFields = changedFields(current, displayName, email, status);
        UserView updated = userRepository.update(userId, displayName, email, status);
        if (updated == null) {
            throw new ApiException(HttpStatus.NOT_FOUND, "USER_NOT_FOUND", "用户不存在");
        }
        String action = status == UserStatus.DISABLED && current.status() != UserStatus.DISABLED
                ? "admin.user.disable"
                : "admin.user.update";
        auditLogService.record(
                actorUserId,
                action,
                "user",
                updated.id(),
                Map.of("username", updated.username(), "changedFields", changedFields),
                httpRequest
        );
        return UserResponse.from(updated);
    }

    @Transactional
    public UserResponse sendInvitation(UUID userId, UUID actorUserId, HttpServletRequest httpRequest) {
        UserView user = requireUser(userId);
        if (user.email() == null || user.email().isBlank()) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "EMAIL_REQUIRED", "邮箱不能为空");
        }
        UserActionTokenService.IssuedToken token = userActionTokenService.issueInvitation(user.id(), actorUserId);
        runAfterCommit(() -> mailDeliveryService.sendInvitation(user.email(), user.username(), invitationUrl(token.plainToken())));
        auditLogService.record(actorUserId, "admin.user.send_invitation", "user", user.id(), Map.of("username", user.username()), httpRequest);
        return UserResponse.from(user);
    }

    @Transactional
    public UserResponse resetPassword(UUID userId, ResetPasswordRequest request, UUID actorUserId, HttpServletRequest httpRequest) {
        UserView current = requireUser(userId);
        passwordPolicy.validate(current.username(), request.newPassword());
        boolean mustChangePassword = request.mustChangePassword() == null || request.mustChangePassword();
        UserView updated = userRepository.resetPassword(userId, passwordEncoder.encode(request.newPassword()), mustChangePassword);
        if (updated == null) {
            throw new ApiException(HttpStatus.NOT_FOUND, "USER_NOT_FOUND", "用户不存在");
        }
        auditLogService.record(
                actorUserId,
                "admin.user.reset_password",
                "user",
                updated.id(),
                Map.of("username", updated.username(), "mustChangePassword", updated.mustChangePassword()),
                httpRequest
        );
        return UserResponse.from(updated);
    }

    private UserView requireUser(UUID userId) {
        return userRepository.findById(userId)
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "USER_NOT_FOUND", "用户不存在"));
    }

    private void rejectCreateForbiddenFields(CreateUserRequest request) {
        if (request.initialPassword() != null
                || request.superAdmin() != null
                || request.passwordHash() != null
                || request.roles() != null
                || request.permissions() != null) {
            throw forbiddenWritableFields();
        }
    }

    private void rejectUpdateForbiddenFields(UpdateUserRequest request) {
        if (request.username() != null
                || request.superAdmin() != null
                || request.mustChangePassword() != null
                || request.passwordHash() != null
                || request.roles() != null
                || request.permissions() != null) {
            throw forbiddenWritableFields();
        }
    }

    private ApiException forbiddenWritableFields() {
        return new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", "请求包含不可写字段");
    }

    private List<String> changedFields(UserView current, String displayName, String email, UserStatus status) {
        List<String> fields = new ArrayList<>();
        if (!equalsNullable(current.displayName(), displayName)) {
            fields.add("displayName");
        }
        if (!equalsNullable(current.email(), email)) {
            fields.add("email");
        }
        if (current.status() != status) {
            fields.add("status");
        }
        return fields;
    }

    private boolean equalsNullable(Object left, Object right) {
        return left == null ? right == null : left.equals(right);
    }

    private String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }

    private String invitationUrl(String token) {
        String baseUrl = mailConfigService.currentConfig().frontendBaseUrl();
        if (baseUrl == null || baseUrl.isBlank()) {
            baseUrl = "http://localhost:3000";
        }
        return baseUrl + "/accept-invitation?token=" + URLEncoder.encode(token, StandardCharsets.UTF_8);
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
}
