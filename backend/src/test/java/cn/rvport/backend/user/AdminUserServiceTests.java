package cn.rvport.backend.user;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.mockito.Mockito.argThat;
import static org.mockito.Mockito.never;

import cn.rvport.backend.audit.AuditLogService;
import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.mail.MailConfig;
import cn.rvport.backend.mail.MailConfigService;
import cn.rvport.backend.mail.MailDeliveryService;
import cn.rvport.backend.useraction.UserActionTokenService;
import cn.rvport.backend.useraction.UserActionTokenType;
import cn.rvport.backend.useraction.UserActionTokenView;
import java.time.OffsetDateTime;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.transaction.support.TransactionSynchronizationManager;

@ExtendWith(MockitoExtension.class)
class AdminUserServiceTests {

    @Mock
    private UserRepository userRepository;

    @Mock
    private PasswordEncoder passwordEncoder;

    @Mock
    private PasswordPolicy passwordPolicy;

    @Mock
    private AuditLogService auditLogService;

    @Mock
    private UserActionTokenService userActionTokenService;

    @Mock
    private MailDeliveryService mailDeliveryService;

    @Mock
    private MailConfigService mailConfigService;

    @InjectMocks
    private AdminUserService adminUserService;

    @Test
    void createsNormalUserAndSendsInvitationWithoutInitialPassword() {
        UUID actorId = UUID.randomUUID();
        UserView created = user("developer", false, true, UserStatus.ACTIVE);
        when(passwordEncoder.encode(any())).thenReturn("hash");
        when(userRepository.create("developer", "Developer", "dev@example.com", "hash", true, UserStatus.ACTIVE))
                .thenReturn(created);
        when(userActionTokenService.issueInvitation(created.id(), actorId)).thenReturn(issuedToken(created.id()));
        when(mailConfigService.currentConfig()).thenReturn(mailConfig());

        MockHttpServletRequest request = new MockHttpServletRequest();
        UserResponse response = adminUserService.create(
                new CreateUserRequest("developer", "Developer", "dev@example.com", null, true, UserStatus.ACTIVE, null, null, null, null),
                actorId,
                request
        );

        assertThat(response.username()).isEqualTo("developer");
        assertThat(response.superAdmin()).isFalse();
        verify(userActionTokenService).issueInvitation(created.id(), actorId);
        verify(auditLogService).record(eq(actorId), eq("admin.user.create"), eq("user"), eq(created.id()), any(), eq(request));
    }

    @Test
    void rejectsSuperAdminWritableFieldOnCreate() {
        assertThatThrownBy(() -> adminUserService.create(
                new CreateUserRequest("developer", "Developer", null, null, true, UserStatus.ACTIVE, true, null, null, null),
                UUID.randomUUID(),
                new MockHttpServletRequest()
        )).isInstanceOf(ApiException.class)
                .hasMessage("请求包含不可写字段");
    }

    @Test
    void updatesAllowedFieldsOnly() {
        UUID actorId = UUID.randomUUID();
        UserView current = user("developer", false, false, UserStatus.ACTIVE);
        UserView updated = new UserView(
                current.id(),
                current.username(),
                "Developer A",
                "dev-a@example.com",
                false,
                false,
                UserStatus.DISABLED,
                current.lastLoginAt(),
                current.createdAt(),
                current.updatedAt()
        );
        when(userRepository.findById(current.id())).thenReturn(Optional.of(current));
        when(userRepository.update(current.id(), "Developer A", "dev-a@example.com", UserStatus.DISABLED))
                .thenReturn(updated);

        UserResponse response = adminUserService.update(
                current.id(),
                new UpdateUserRequest("Developer A", "dev-a@example.com", UserStatus.DISABLED, null, null, null, null, null, null),
                actorId,
                new MockHttpServletRequest()
        );

        assertThat(response.status()).isEqualTo(UserStatus.DISABLED);
        verify(auditLogService).record(eq(actorId), eq("admin.user.disable"), eq("user"), eq(current.id()), any(), any());
    }

    @Test
    void resetPasswordSetsMustChangePasswordByDefault() {
        UUID actorId = UUID.randomUUID();
        UserView current = user("developer", false, false, UserStatus.ACTIVE);
        UserView updated = new UserView(
                current.id(),
                current.username(),
                current.displayName(),
                current.email(),
                false,
                true,
                UserStatus.ACTIVE,
                current.lastLoginAt(),
                current.createdAt(),
                current.updatedAt()
        );
        when(userRepository.findById(current.id())).thenReturn(Optional.of(current));
        when(passwordEncoder.encode("NewPass123")).thenReturn("new-hash");
        when(userRepository.resetPassword(current.id(), "new-hash", true)).thenReturn(updated);

        UserResponse response = adminUserService.resetPassword(
                current.id(),
                new ResetPasswordRequest("NewPass123", null),
                actorId,
                new MockHttpServletRequest()
        );

        assertThat(response.mustChangePassword()).isTrue();
        verify(passwordPolicy).validate("developer", "NewPass123");
    }

    @Test
    void createRejectsDuplicateUsernameOrEmailAndMissingEmail() {
        assertThatThrownBy(() -> adminUserService.create(
                new CreateUserRequest("developer", "Developer", null, null, true, UserStatus.ACTIVE, null, null, null, null),
                UUID.randomUUID(),
                new MockHttpServletRequest()
        )).isInstanceOf(ApiException.class)
                .hasMessage("邮箱不能为空");

        when(userRepository.existsByUsername("developer")).thenReturn(true);

        assertThatThrownBy(() -> adminUserService.create(
                new CreateUserRequest("developer", "Developer", "dev@example.com", null, true, UserStatus.ACTIVE, null, null, null, null),
                UUID.randomUUID(),
                new MockHttpServletRequest()
        )).isInstanceOf(ApiException.class)
                .hasMessage("用户名已存在");

        when(userRepository.existsByUsername("developer")).thenReturn(false);
        when(userRepository.existsByEmail("dev@example.com")).thenReturn(true);

        assertThatThrownBy(() -> adminUserService.create(
                new CreateUserRequest("developer", "Developer", "dev@example.com", null, true, UserStatus.ACTIVE, null, null, null, null),
                UUID.randomUUID(),
                new MockHttpServletRequest()
        )).isInstanceOf(ApiException.class)
                .hasMessage("邮箱已存在");
    }

    @Test
    void getUpdateAndResetRejectMissingUser() {
        UUID userId = UUID.randomUUID();
        when(userRepository.findById(userId)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> adminUserService.get(userId))
                .isInstanceOf(ApiException.class)
                .hasMessage("用户不存在");
        assertThatThrownBy(() -> adminUserService.update(
                userId,
                new UpdateUserRequest("Developer", null, null, null, null, null, null, null, null),
                UUID.randomUUID(),
                new MockHttpServletRequest()
        )).isInstanceOf(ApiException.class)
                .hasMessage("用户不存在");
        assertThatThrownBy(() -> adminUserService.resetPassword(
                userId,
                new ResetPasswordRequest("NewPass123", true),
                UUID.randomUUID(),
                new MockHttpServletRequest()
        )).isInstanceOf(ApiException.class)
                .hasMessage("用户不存在");
    }

    @Test
    void updateRejectsForbiddenWritableFields() {
        UUID userId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        UpdateUserRequest[] requests = {
                new UpdateUserRequest(null, null, null, "new-name", null, null, null, null, null),
                new UpdateUserRequest(null, null, null, null, true, null, null, null, null),
                new UpdateUserRequest(null, null, null, null, null, true, null, null, null),
                new UpdateUserRequest(null, null, null, null, null, null, "hash", null, null),
                new UpdateUserRequest(null, null, null, null, null, null, null, java.util.List.of("admin"), null),
                new UpdateUserRequest(null, null, null, null, null, null, null, null, java.util.List.of("user:write"))
        };

        for (UpdateUserRequest request : requests) {
            assertThatThrownBy(() -> adminUserService.update(userId, request, actorId, new MockHttpServletRequest()))
                    .isInstanceOf(ApiException.class)
                    .hasMessage("请求包含不可写字段");
        }
    }

    @Test
    void createAndResetHandleBlankFieldsAndExplicitMustChangeFalse() {
        UUID actorId = UUID.randomUUID();
        UserView created = user("developer", false, false, UserStatus.ACTIVE);
        when(passwordEncoder.encode(any())).thenReturn("hash");
        when(userRepository.create("developer", null, "dev@example.com", "hash", false, UserStatus.ACTIVE)).thenReturn(created);
        when(userActionTokenService.issueInvitation(created.id(), actorId)).thenReturn(issuedToken(created.id()));
        when(mailConfigService.currentConfig()).thenReturn(mailConfig());

        UserResponse response = adminUserService.create(
                new CreateUserRequest(" developer ", "   ", "dev@example.com", null, false, null, null, null, null, null),
                actorId,
                new MockHttpServletRequest()
        );

        assertThat(response.mustChangePassword()).isFalse();
        verify(userRepository).create("developer", null, "dev@example.com", "hash", false, UserStatus.ACTIVE);

        UserView updated = new UserView(created.id(), created.username(), created.displayName(), created.email(), false,
                false, UserStatus.ACTIVE, created.lastLoginAt(), created.createdAt(), created.updatedAt());
        when(userRepository.findById(created.id())).thenReturn(Optional.of(created));
        when(passwordEncoder.encode("NewPass123")).thenReturn("new-hash");
        when(userRepository.resetPassword(created.id(), "new-hash", false)).thenReturn(updated);

        UserResponse reset = adminUserService.resetPassword(
                created.id(),
                new ResetPasswordRequest("NewPass123", false),
                actorId,
                new MockHttpServletRequest()
        );

        assertThat(reset.mustChangePassword()).isFalse();
        verify(auditLogService).record(eq(actorId), eq("admin.user.reset_password"), eq("user"), eq(created.id()),
                argThat(details -> Boolean.FALSE.equals(details.get("mustChangePassword"))), any());
        verify(mailDeliveryService, never()).sendPasswordReset(any(), any());
    }

    @Test
    void createRejectsInitialPasswordWritableField() {
        assertThatThrownBy(() -> adminUserService.create(
                new CreateUserRequest("developer", "Developer", "dev@example.com", "DevPass123", true, UserStatus.ACTIVE, null, null, null, null),
                UUID.randomUUID(),
                new MockHttpServletRequest()
        )).isInstanceOf(ApiException.class)
                .hasMessage("请求包含不可写字段");
    }

    @Test
    void resendInvitationRequiresEmailAndIssuesNewToken() {
        UUID actorId = UUID.randomUUID();
        UserView current = user("developer", false, false, UserStatus.ACTIVE);
        when(userRepository.findById(current.id())).thenReturn(Optional.of(current));
        when(userActionTokenService.issueInvitation(current.id(), actorId)).thenReturn(issuedToken(current.id()));
        when(mailConfigService.currentConfig()).thenReturn(mailConfig());

        UserResponse response = adminUserService.sendInvitation(current.id(), actorId, new MockHttpServletRequest());

        assertThat(response.email()).isEqualTo("dev@example.com");
        verify(userActionTokenService).issueInvitation(current.id(), actorId);
    }

    @Test
    void updateInheritsOmittedFieldsAndUsesUpdateAuditForUnchangedActiveUser() {
        UUID actorId = UUID.randomUUID();
        UserView current = new UserView(UUID.randomUUID(), "developer", null, null, false, false,
                UserStatus.ACTIVE, null, OffsetDateTime.now(), OffsetDateTime.now());
        when(userRepository.findById(current.id())).thenReturn(Optional.of(current));
        when(userRepository.update(current.id(), null, null, UserStatus.ACTIVE)).thenReturn(current);

        UserResponse response = adminUserService.update(current.id(),
                new UpdateUserRequest(null, null, null, null, null, null, null, null, null),
                actorId, new MockHttpServletRequest());

        assertThat(response.email()).isNull();
        verify(auditLogService).record(eq(actorId), eq("admin.user.update"), eq("user"), eq(current.id()),
                argThat(details -> ((java.util.List<?>) details.get("changedFields")).isEmpty()), any());
    }

    @Test
    void updateRejectsDuplicateEmailAndMissingRowAfterRead() {
        UserView current = user("developer", false, false, UserStatus.ACTIVE);
        when(userRepository.findById(current.id())).thenReturn(Optional.of(current));
        when(userRepository.existsByEmailExcludingId("taken@example.com", current.id())).thenReturn(true);
        assertThatThrownBy(() -> adminUserService.update(current.id(),
                new UpdateUserRequest(null, "taken@example.com", null, null, null, null, null, null, null),
                UUID.randomUUID(), new MockHttpServletRequest()))
                .isInstanceOf(ApiException.class).hasMessage("邮箱已存在");

        when(userRepository.existsByEmailExcludingId("new@example.com", current.id())).thenReturn(false);
        when(userRepository.update(current.id(), current.displayName(), "new@example.com", current.status())).thenReturn(null);
        assertThatThrownBy(() -> adminUserService.update(current.id(),
                new UpdateUserRequest(null, "new@example.com", null, null, null, null, null, null, null),
                UUID.randomUUID(), new MockHttpServletRequest()))
                .isInstanceOf(ApiException.class).hasMessage("用户不存在");
    }

    @Test
    void resetPasswordRejectsRowRemovedAfterInitialRead() {
        UserView current = user("developer", false, false, UserStatus.ACTIVE);
        when(userRepository.findById(current.id())).thenReturn(Optional.of(current));
        when(passwordEncoder.encode("NewPass123")).thenReturn("hash");
        when(userRepository.resetPassword(current.id(), "hash", true)).thenReturn(null);

        assertThatThrownBy(() -> adminUserService.resetPassword(current.id(), new ResetPasswordRequest("NewPass123", null),
                UUID.randomUUID(), new MockHttpServletRequest()))
                .isInstanceOf(ApiException.class).hasMessage("用户不存在");
    }

    @Test
    void invitationRejectsNullAndBlankEmail() {
        UserView nullEmail = new UserView(UUID.randomUUID(), "null-mail", null, null, false, false,
                UserStatus.ACTIVE, null, OffsetDateTime.now(), OffsetDateTime.now());
        UserView blankEmail = new UserView(UUID.randomUUID(), "blank-mail", null, "  ", false, false,
                UserStatus.ACTIVE, null, OffsetDateTime.now(), OffsetDateTime.now());
        when(userRepository.findById(nullEmail.id())).thenReturn(Optional.of(nullEmail));
        when(userRepository.findById(blankEmail.id())).thenReturn(Optional.of(blankEmail));

        assertThatThrownBy(() -> adminUserService.sendInvitation(nullEmail.id(), UUID.randomUUID(), new MockHttpServletRequest()))
                .isInstanceOf(ApiException.class).hasMessage("邮箱不能为空");
        assertThatThrownBy(() -> adminUserService.sendInvitation(blankEmail.id(), UUID.randomUUID(), new MockHttpServletRequest()))
                .isInstanceOf(ApiException.class).hasMessage("邮箱不能为空");
    }

    @Test
    void defersInvitationDeliveryUntilTransactionCommitAndUsesDefaultFrontendUrl() {
        UUID actorId = UUID.randomUUID();
        UserView created = user("developer", false, true, UserStatus.ACTIVE);
        when(passwordEncoder.encode(any())).thenReturn("hash");
        when(userRepository.create("developer", null, "dev@example.com", "hash", true, UserStatus.ACTIVE)).thenReturn(created);
        when(userActionTokenService.issueInvitation(created.id(), actorId)).thenReturn(issuedToken(created.id()));
        when(mailConfigService.currentConfig()).thenReturn(new MailConfig(true, true, null, 0, null, null,
                "noreply@example.com", true, false, 5000, 10000, " "));
        TransactionSynchronizationManager.initSynchronization();
        try {
            adminUserService.create(new CreateUserRequest("developer", null, "dev@example.com", null,
                    null, null, null, null, null, null), actorId, new MockHttpServletRequest());
            verify(mailDeliveryService, never()).sendInvitation(any(), any(), any());
            TransactionSynchronizationManager.getSynchronizations().forEach(
                    org.springframework.transaction.support.TransactionSynchronization::afterCommit);
            verify(mailDeliveryService).sendInvitation(eq("dev@example.com"), eq("developer"),
                    org.mockito.ArgumentMatchers.contains("http://localhost:3000/accept-invitation"));
        } finally {
            TransactionSynchronizationManager.clearSynchronization();
        }
    }

    private UserView user(String username, boolean superAdmin, boolean mustChangePassword, UserStatus status) {
        return new UserView(
                UUID.randomUUID(),
                username,
                "Developer",
                "dev@example.com",
                superAdmin,
                mustChangePassword,
                status,
                null,
                OffsetDateTime.now(),
                OffsetDateTime.now()
        );
    }

    private UserActionTokenService.IssuedToken issuedToken(UUID userId) {
        return new UserActionTokenService.IssuedToken(
                "plain-token",
                new UserActionTokenView(UUID.randomUUID(), userId, UserActionTokenType.INVITATION, "hash",
                        OffsetDateTime.now().plusHours(1), null, UUID.randomUUID(), OffsetDateTime.now())
        );
    }

    private MailConfig mailConfig() {
        return new MailConfig(true, true, null, 0, null, null, "noreply@example.com", true, false, 5000, 10000, "http://localhost:3000");
    }
}
