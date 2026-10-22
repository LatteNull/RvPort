package cn.rvport.backend.auth;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.argThat;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.when;

import cn.rvport.backend.audit.AuditLogService;
import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.mail.MailConfig;
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
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

@ExtendWith(MockitoExtension.class)
class AuthServiceTests {

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
    private AuthService authService;

    @Test
    void loginCreatesSecuritySessionAndReturnsUser() {
        UserView user = user(true);
        when(userRepository.findByUsernameWithPassword("admin"))
                .thenReturn(Optional.of(new UserWithPassword(user, "hash")));
        when(passwordEncoder.matches("Admin123", "hash")).thenReturn(true);
        when(userRepository.findById(user.id())).thenReturn(Optional.of(user));

        MockHttpServletRequest request = new MockHttpServletRequest();
        LoginResponse response = authService.login(new LoginRequest("admin", "Admin123"), request);

        assertThat(response.user().username()).isEqualTo("admin");
        assertThat(response.user().superAdmin()).isTrue();
        assertThat(request.getSession(false)).isNotNull();
        assertThat(SecurityContextHolder.getContext().getAuthentication()).isNotNull();
        verify(userRepository).updateLastLoginAt(user.id());
        verify(auditLogService).record(eq(user.id()), eq("auth.login.success"), eq("user"), eq(user.id()), any(), eq(request));
    }

    @Test
    void loginRejectsWrongPassword() {
        UserView user = user(false);
        when(userRepository.findByUsernameWithPassword("admin"))
                .thenReturn(Optional.of(new UserWithPassword(user, "hash")));
        when(passwordEncoder.matches("bad", "hash")).thenReturn(false);

        assertThatThrownBy(() -> authService.login(new LoginRequest("admin", "bad"), new MockHttpServletRequest()))
                .isInstanceOf(ApiException.class)
                .hasMessage("用户名或密码错误");
    }

    @Test
    void loginRejectsUnknownUserAndFallsBackToOriginalViewAfterSuccess() {
        MockHttpServletRequest missingRequest = new MockHttpServletRequest();
        when(userRepository.findByUsernameWithPassword("missing")).thenReturn(Optional.empty());
        assertThatThrownBy(() -> authService.login(new LoginRequest("missing", "Password123"), missingRequest))
                .isInstanceOf(ApiException.class).hasMessage("用户名或密码错误");
        verify(passwordEncoder, never()).matches(eq("Password123"), any());

        UserView user = user(false);
        when(userRepository.findByUsernameWithPassword("admin"))
                .thenReturn(Optional.of(new UserWithPassword(user, "hash")));
        when(passwordEncoder.matches("Admin123", "hash")).thenReturn(true);
        when(userRepository.findById(user.id())).thenReturn(Optional.empty());
        assertThat(authService.login(new LoginRequest("admin", "Admin123"), new MockHttpServletRequest())
                .user().id()).isEqualTo(user.id());
    }

    @Test
    void loginRejectsDisabledUserAndAuditsReason() {
        UserView disabled = new UserView(
                UUID.randomUUID(),
                "disabled",
                "Disabled",
                null,
                false,
                false,
                UserStatus.DISABLED,
                null,
                OffsetDateTime.now(),
                OffsetDateTime.now()
        );
        when(userRepository.findByUsernameWithPassword("disabled"))
                .thenReturn(Optional.of(new UserWithPassword(disabled, "hash")));
        when(passwordEncoder.matches("Disabled123", "hash")).thenReturn(true);
        MockHttpServletRequest request = new MockHttpServletRequest();

        assertThatThrownBy(() -> authService.login(new LoginRequest("disabled", "Disabled123"), request))
                .isInstanceOf(ApiException.class)
                .hasMessage("用户已禁用");

        verify(userRepository, never()).updateLastLoginAt(disabled.id());
        verify(auditLogService).record(eq(disabled.id()), eq("auth.login.failed"), eq("user"), eq(disabled.id()),
                argThat(details -> "disabled".equals(details.get("reason"))), eq(request));
    }

    @Test
    void changePasswordValidatesCurrentPasswordAndClearsMustChangePassword() {
        UserView oldUser = user(false);
        UserView updated = new UserView(
                oldUser.id(),
                oldUser.username(),
                oldUser.displayName(),
                oldUser.email(),
                false,
                false,
                UserStatus.ACTIVE,
                oldUser.lastLoginAt(),
                oldUser.createdAt(),
                oldUser.updatedAt()
        );
        when(userRepository.findByIdWithPassword(oldUser.id()))
                .thenReturn(Optional.of(new UserWithPassword(oldUser, "old-hash")));
        when(passwordEncoder.matches("OldPass123", "old-hash")).thenReturn(true);
        when(passwordEncoder.encode("NewPass123")).thenReturn("new-hash");
        when(userRepository.changeOwnPassword(oldUser.id(), "new-hash")).thenReturn(updated);

        MockHttpServletRequest request = new MockHttpServletRequest();
        var response = authService.changePassword(
                RvPortUserPrincipal.from(oldUser),
                new ChangePasswordRequest("OldPass123", "NewPass123"),
                request
        );

        assertThat(response.mustChangePassword()).isFalse();
        verify(passwordPolicy).validate(oldUser.username(), "NewPass123");
        verify(auditLogService).record(eq(oldUser.id()), eq("auth.change_password"), eq("user"), eq(oldUser.id()), any(), eq(request));
    }

    @Test
    void changePasswordRejectsMissingOrDisabledSessionUser() {
        UserView disabled = user(false);
        UserWithPassword withPassword = new UserWithPassword(disabled, "hash");
        when(userRepository.findByIdWithPassword(disabled.id())).thenReturn(Optional.empty());

        assertThatThrownBy(() -> authService.changePassword(
                RvPortUserPrincipal.from(disabled),
                new ChangePasswordRequest("OldPass123", "NewPass123"),
                new MockHttpServletRequest()
        )).isInstanceOf(ApiException.class)
                .hasMessage("登录态已失效");

        when(userRepository.findByIdWithPassword(disabled.id())).thenReturn(Optional.of(withPassword));
        UserView disabledView = new UserView(disabled.id(), disabled.username(), disabled.displayName(), disabled.email(),
                disabled.superAdmin(), disabled.mustChangePassword(), UserStatus.DISABLED, disabled.lastLoginAt(),
                disabled.createdAt(), disabled.updatedAt());
        when(userRepository.findByIdWithPassword(disabled.id())).thenReturn(Optional.of(new UserWithPassword(disabledView, "hash")));

        assertThatThrownBy(() -> authService.changePassword(
                RvPortUserPrincipal.from(disabled),
                new ChangePasswordRequest("OldPass123", "NewPass123"),
                new MockHttpServletRequest()
        )).isInstanceOf(ApiException.class)
                .hasMessage("登录态已失效");
    }

    @Test
    void changePasswordRejectsWrongCurrentPassword() {
        UserView user = user(false);
        when(userRepository.findByIdWithPassword(user.id())).thenReturn(Optional.of(new UserWithPassword(user, "old-hash")));
        when(passwordEncoder.matches("BadPass123", "old-hash")).thenReturn(false);

        assertThatThrownBy(() -> authService.changePassword(
                RvPortUserPrincipal.from(user),
                new ChangePasswordRequest("BadPass123", "NewPass123"),
                new MockHttpServletRequest()
        )).isInstanceOf(ApiException.class)
                .hasMessage("当前密码不正确");

        verify(passwordPolicy, never()).validate(any(), any());
        verify(userRepository, never()).changeOwnPassword(any(), any());
    }

    @Test
    void currentUserRejectsMissingOrDisabledPrincipalUser() {
        UserView user = user(false);
        when(userRepository.findById(user.id())).thenReturn(Optional.empty());

        assertThatThrownBy(() -> authService.currentUser(RvPortUserPrincipal.from(user)))
                .isInstanceOf(ApiException.class)
                .hasMessage("登录态已失效");

        UserView disabled = new UserView(user.id(), user.username(), user.displayName(), user.email(), false, false,
                UserStatus.DISABLED, user.lastLoginAt(), user.createdAt(), user.updatedAt());
        when(userRepository.findById(user.id())).thenReturn(Optional.of(disabled));

        assertThatThrownBy(() -> authService.currentUser(RvPortUserPrincipal.from(user)))
                .isInstanceOf(ApiException.class)
                .hasMessage("登录态已失效");
    }

    @Test
    void currentUserAndProfileUpdateHandleDisplayNameAndReadonlyFields() {
        UserView current = user(false);
        when(userRepository.findById(current.id())).thenReturn(Optional.of(current));
        assertThat(authService.currentUser(RvPortUserPrincipal.from(current)).id()).isEqualTo(current.id());

        UserView renamed = new UserView(current.id(), current.username(), "Renamed", current.email(), false, false,
                UserStatus.ACTIVE, current.lastLoginAt(), current.createdAt(), current.updatedAt());
        when(userRepository.updateProfile(current.id(), "Renamed")).thenReturn(renamed);
        var response = authService.updateProfile(RvPortUserPrincipal.from(current),
                new UpdateProfileRequest(" Renamed ", null, null, null, null, null, null), new MockHttpServletRequest());
        assertThat(response.displayName()).isEqualTo("Renamed");

        when(userRepository.updateProfile(current.id(), current.displayName())).thenReturn(current);
        assertThat(authService.updateProfile(RvPortUserPrincipal.from(current),
                new UpdateProfileRequest(null, null, null, null, null, null, null), new MockHttpServletRequest())
                .displayName()).isEqualTo(current.displayName());
        when(userRepository.updateProfile(current.id(), null)).thenReturn(renamed);
        authService.updateProfile(RvPortUserPrincipal.from(current),
                new UpdateProfileRequest(" ", null, null, null, null, null, null), new MockHttpServletRequest());

        List<UpdateProfileRequest> forbidden = List.of(
                new UpdateProfileRequest(null, "name", null, null, null, null, null),
                new UpdateProfileRequest(null, null, "mail@example.com", null, null, null, null),
                new UpdateProfileRequest(null, null, null, true, null, null, null),
                new UpdateProfileRequest(null, null, null, null, "DISABLED", null, null),
                new UpdateProfileRequest(null, null, null, null, null, true, null),
                new UpdateProfileRequest(null, null, null, null, null, null, "hash")
        );
        forbidden.forEach(request -> assertThatThrownBy(() -> authService.updateProfile(
                RvPortUserPrincipal.from(current), request, new MockHttpServletRequest()))
                .isInstanceOf(ApiException.class).hasMessage("请求包含不可写字段"));
    }

    @Test
    void acceptsInvitationSetsPasswordAndConsumesToken() {
        UserView user = user(false);
        UserActionTokenView token = token(user.id(), UserActionTokenType.INVITATION);
        when(userActionTokenService.requireOpen("token", UserActionTokenType.INVITATION)).thenReturn(token);
        when(userRepository.findById(user.id())).thenReturn(Optional.of(user));
        when(passwordEncoder.encode("NewPass123")).thenReturn("hash");
        when(userRepository.resetPassword(user.id(), "hash", false)).thenReturn(user);

        UserResponse response = authService.acceptInvitation(new AcceptInvitationRequest("token", "NewPass123"), new MockHttpServletRequest());

        assertThat(response.username()).isEqualTo("admin");
        verify(passwordPolicy).validate("admin", "NewPass123");
        verify(userActionTokenService).consume(token.id());
    }

    @Test
    void passwordResetRequestDoesNotRevealMissingUser() {
        when(userRepository.findByUsernameOrEmail("missing@example.com")).thenReturn(Optional.empty());

        authService.requestPasswordReset(new PasswordResetRequest("missing@example.com"), new MockHttpServletRequest());

        verify(userActionTokenService, never()).issuePasswordReset(any());
        verify(mailDeliveryService, never()).sendPasswordReset(any(), any());
    }

    @Test
    void passwordResetRequestSilentlyIgnoresUnavailableRecipients() {
        UserView active = user(false);
        UserView disabled = new UserView(active.id(), active.username(), active.displayName(), active.email(), false,
                false, UserStatus.DISABLED, null, active.createdAt(), active.updatedAt());
        UserView noEmail = new UserView(UUID.randomUUID(), "no-email", null, null, false, false,
                UserStatus.ACTIVE, null, OffsetDateTime.now(), OffsetDateTime.now());
        UserView blankEmail = new UserView(UUID.randomUUID(), "blank-email", null, " ", false, false,
                UserStatus.ACTIVE, null, OffsetDateTime.now(), OffsetDateTime.now());
        when(userRepository.findByUsernameOrEmail("disabled")).thenReturn(Optional.of(disabled));
        when(userRepository.findByUsernameOrEmail("no-email")).thenReturn(Optional.of(noEmail));
        when(userRepository.findByUsernameOrEmail("blank-email")).thenReturn(Optional.of(blankEmail));

        for (String identifier : List.of("disabled", "no-email", "blank-email")) {
            authService.requestPasswordReset(new PasswordResetRequest(identifier), new MockHttpServletRequest());
        }
        verify(userActionTokenService, never()).issuePasswordReset(any());
    }

    @Test
    void passwordResetMailUsesConfiguredOrDefaultUrlAndRunsAfterCommit() {
        UserView base = user(false);
        UserView active = new UserView(base.id(), base.username(), base.displayName(), "admin@example.com",
                false, false, UserStatus.ACTIVE, null, base.createdAt(), base.updatedAt());
        when(userRepository.findByUsernameOrEmail("admin")).thenReturn(Optional.of(active));
        UserActionTokenView token = token(active.id(), UserActionTokenType.PASSWORD_RESET);
        when(userActionTokenService.issuePasswordReset(active.id()))
                .thenReturn(new UserActionTokenService.IssuedToken("token with space", token));
        when(mailConfigService.currentConfig()).thenReturn(mailConfig("https://frontend.example/app"));

        authService.requestPasswordReset(new PasswordResetRequest("admin"), new MockHttpServletRequest());
        verify(mailDeliveryService).sendPasswordReset(active.email(),
                "https://frontend.example/app/reset-password?token=token+with+space");

        org.mockito.Mockito.clearInvocations(mailDeliveryService);
        when(mailConfigService.currentConfig()).thenReturn(mailConfig(" "));
        TransactionSynchronizationManager.initSynchronization();
        try {
            authService.requestPasswordReset(new PasswordResetRequest("admin"), new MockHttpServletRequest());
            verify(mailDeliveryService, never()).sendPasswordReset(any(), any());
            List<TransactionSynchronization> synchronizations = TransactionSynchronizationManager.getSynchronizations();
            assertThat(synchronizations).hasSize(1);
            synchronizations.getFirst().afterCommit();
            verify(mailDeliveryService).sendPasswordReset(active.email(),
                    "http://localhost:3000/reset-password?token=token+with+space");
        } finally {
            TransactionSynchronizationManager.clearSynchronization();
        }
    }

    @Test
    void passwordResetConfirmSetsPasswordAndConsumesToken() {
        UserView user = user(false);
        UserView updated = new UserView(user.id(), user.username(), user.displayName(), user.email(),
                user.superAdmin(), false, user.status(), user.lastLoginAt(), user.createdAt(), user.updatedAt());
        UserActionTokenView token = token(user.id(), UserActionTokenType.PASSWORD_RESET);
        when(userActionTokenService.requireOpen("token", UserActionTokenType.PASSWORD_RESET)).thenReturn(token);
        when(userRepository.findById(user.id())).thenReturn(Optional.of(user));
        when(passwordEncoder.encode("NewPass123")).thenReturn("hash");
        when(userRepository.resetPassword(user.id(), "hash", false)).thenReturn(updated);

        UserResponse response = authService.confirmPasswordReset(new PasswordResetConfirmRequest("token", "NewPass123"), new MockHttpServletRequest());

        assertThat(response.mustChangePassword()).isFalse();
        verify(userActionTokenService).consume(token.id());
    }

    @Test
    void updateProfileRejectsUsernameAndEmail() {
        UserView user = user(false);

        assertThatThrownBy(() -> authService.updateProfile(
                RvPortUserPrincipal.from(user),
                new UpdateProfileRequest("Admin A", "new", null, null, null, null, null),
                new MockHttpServletRequest()
        )).isInstanceOf(ApiException.class)
                .hasMessage("请求包含不可写字段");
    }

    private UserView user(boolean superAdmin) {
        return new UserView(
                UUID.randomUUID(),
                "admin",
                "Admin",
                null,
                superAdmin,
                true,
                UserStatus.ACTIVE,
                null,
                OffsetDateTime.now(),
                OffsetDateTime.now()
        );
    }

    private UserActionTokenView token(UUID userId, UserActionTokenType type) {
        return new UserActionTokenView(UUID.randomUUID(), userId, type, "hash",
                OffsetDateTime.now().plusHours(1), null, null, OffsetDateTime.now());
    }

    private MailConfig mailConfig() {
        return new MailConfig(true, true, null, 0, null, null, "noreply@example.com", true, false, 5000, 10000, "http://localhost:3000");
    }

    private MailConfig mailConfig(String frontendBaseUrl) {
        return new MailConfig(true, true, null, 0, null, null, "noreply@example.com", true, false,
                5000, 10000, frontendBaseUrl);
    }
}
