package cn.rvport.backend.mail;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.mail.MailSendException;
import org.springframework.mail.javamail.JavaMailSenderImpl;

@ExtendWith(MockitoExtension.class)
class MailDeliveryServiceTests {

    @Mock
    private MailConfigService mailConfigService;

    @Test
    void sendsConfiguredMessagesInTestMode() {
        MailDeliveryService service = new MailDeliveryService(mailConfigService);
        when(mailConfigService.currentConfig()).thenReturn(testModeConfig(true));

        MailSendResult result = service.sendInvitation(
                "dev@example.com",
                "developer",
                "http://localhost:3000/invitations/accept?token=token"
        );

        assertThat(result.success()).isTrue();
    }

    @Test
    void returnsFailureWhenMailIsDisabled() {
        MailDeliveryService service = new MailDeliveryService(mailConfigService);
        MailConfig disabled = testModeConfig(false);
        when(mailConfigService.currentConfig()).thenReturn(disabled);
        org.mockito.Mockito.doThrow(new cn.rvport.backend.common.error.ApiException(
                org.springframework.http.HttpStatus.BAD_REQUEST,
                "MAIL_DISABLED",
                "邮箱服务未启用"
        )).when(mailConfigService).validateSendable(disabled);

        MailSendResult result = service.sendPasswordReset(
                "dev@example.com",
                "http://localhost:3000/password-resets/confirm?token=token"
        );

        assertThat(result.success()).isFalse();
        assertThat(result.message()).isEqualTo("邮箱服务未启用");
    }

    @Test
    void testMailCanUseTemporarySettings() {
        MailDeliveryService service = new MailDeliveryService(mailConfigService);
        when(mailConfigService.currentConfig()).thenReturn(testModeConfig(false));

        MailSendResult result = service.sendTest("dev@example.com", new MailSettingsRequest(
                true,
                true,
                null,
                null,
                null,
                null,
                "noreply@example.com",
                null,
                null,
                null,
                null,
                null
        ));

        assertThat(result.success()).isTrue();
    }

    @Test
    void sendsPasswordResetAndTaskCompletionInTestMode() {
        MailDeliveryService service = new MailDeliveryService(mailConfigService);
        MailConfig config = testModeConfig(true);
        when(mailConfigService.currentConfig()).thenReturn(config);

        assertThat(service.sendPasswordReset("dev@example.com", "https://example.test/reset").success()).isTrue();
        assertThat(service.sendTaskCompleted("dev@example.com", "task done", "body").success()).isTrue();
        verify(mailConfigService, org.mockito.Mockito.times(2)).validateSendable(config);
    }

    @Test
    void configuredSendReturnsValidationFailureWithoutUsingExternalMailServer() {
        MailDeliveryService service = new MailDeliveryService(mailConfigService);
        MailConfig config = testModeConfig(true);
        when(mailConfigService.currentConfig()).thenReturn(config);
        doThrow(new cn.rvport.backend.common.error.ApiException(
                org.springframework.http.HttpStatus.BAD_REQUEST, "MAIL_CONFIG_INVALID", "配置不可用"))
                .when(mailConfigService).validateSendable(config);

        MailSendResult result = service.sendTaskCompleted("dev@example.com", "done", "body");

        assertThat(result.success()).isFalse();
        assertThat(result.message()).isEqualTo("配置不可用");
    }

    @Test
    void temporarySettingsOverrideEverySupportedValueAndTrimText() {
        MailDeliveryService service = new MailDeliveryService(mailConfigService);
        MailConfig current = new MailConfig(false, false, "old", 25, "old-user", "old-pass",
                "old@example.com", false, true, 1, 2, "https://old.example");
        when(mailConfigService.currentConfig()).thenReturn(current);
        MailSettingsRequest request = new MailSettingsRequest(true, true, " smtp.example.com ", 587,
                " new-user ", "new-pass", " sender@example.com ", true, false, 3000, 4000,
                " https://frontend.example ");

        assertThat(service.sendTest("dev@example.com", request).success()).isTrue();

        org.mockito.ArgumentCaptor<MailConfig> captor = org.mockito.ArgumentCaptor.forClass(MailConfig.class);
        verify(mailConfigService).validateSendable(captor.capture());
        assertThat(captor.getValue()).satisfies(config -> {
            assertThat(config.host()).isEqualTo("smtp.example.com");
            assertThat(config.port()).isEqualTo(587);
            assertThat(config.username()).isEqualTo("new-user");
            assertThat(config.password()).isEqualTo("new-pass");
            assertThat(config.fromAddress()).isEqualTo("sender@example.com");
            assertThat(config.connectionTimeoutMillis()).isEqualTo(3000);
            assertThat(config.readTimeoutMillis()).isEqualTo(4000);
        });
    }

    @Test
    void blankTemporaryPasswordAndValuesFallBackToCurrentConfiguration() {
        MailDeliveryService service = new MailDeliveryService(mailConfigService);
        MailConfig current = testModeConfig(true);
        when(mailConfigService.currentConfig()).thenReturn(current);

        MailSendResult result = service.sendTest("dev@example.com", new MailSettingsRequest(
                null, null, " ", null, null, " ", null, null, null, null, null, null));

        assertThat(result.success()).isTrue();
        org.mockito.ArgumentCaptor<MailConfig> captor = org.mockito.ArgumentCaptor.forClass(MailConfig.class);
        verify(mailConfigService).validateSendable(captor.capture());
        assertThat(captor.getValue().password()).isEqualTo(current.password());
        assertThat(captor.getValue().frontendBaseUrl()).isEqualTo(current.frontendBaseUrl());
    }

    @Test
    void sendsRealMessageThroughInjectedSender() {
        JavaMailSenderImpl sender = org.mockito.Mockito.mock(JavaMailSenderImpl.class);
        MailDeliveryService service = new MailDeliveryService(mailConfigService, ignored -> sender);
        MailConfig config = realConfig("user");
        when(mailConfigService.currentConfig()).thenReturn(config);

        MailSendResult result = service.sendTaskCompleted("to@example.com", "subject", "body");

        assertThat(result.success()).isTrue();
        org.mockito.ArgumentCaptor<org.springframework.mail.SimpleMailMessage> captor =
                org.mockito.ArgumentCaptor.forClass(org.springframework.mail.SimpleMailMessage.class);
        verify(sender).send(captor.capture());
        assertThat(captor.getValue().getFrom()).isEqualTo("from@example.com");
        assertThat(captor.getValue().getTo()).containsExactly("to@example.com");
        assertThat(captor.getValue().getSubject()).isEqualTo("subject");
        assertThat(captor.getValue().getText()).isEqualTo("body");
    }

    @Test
    void sanitizesMailFailureAndHandlesMissingMessage() {
        JavaMailSenderImpl sender = org.mockito.Mockito.mock(JavaMailSenderImpl.class);
        MailDeliveryService service = new MailDeliveryService(mailConfigService, ignored -> sender);
        MailConfig config = realConfig("user");
        when(mailConfigService.currentConfig()).thenReturn(config);
        doThrow(new MailSendException("password=plain token=abc secret=value"))
                .when(sender).send(any(org.springframework.mail.SimpleMailMessage.class));

        MailSendResult sanitized = service.sendTest("to@example.com", null);

        assertThat(sanitized.success()).isFalse();
        assertThat(sanitized.message()).contains("password=******", "token=******", "secret=******");

        doThrow(new MailSendException((String) null))
                .when(sender).send(any(org.springframework.mail.SimpleMailMessage.class));
        assertThat(service.sendTest("to@example.com", null).message()).isEqualTo("邮件发送失败");
    }

    @Test
    void createsSenderWithConfiguredPropertiesAndAuthenticationFlag() {
        MailDeliveryService service = new MailDeliveryService(mailConfigService);

        JavaMailSenderImpl authenticated = service.sender(realConfig(" user "));
        JavaMailSenderImpl anonymous = service.sender(realConfig(" "));

        assertThat(authenticated.getHost()).isEqualTo("smtp.example.com");
        assertThat(authenticated.getPort()).isEqualTo(2525);
        assertThat(authenticated.getUsername()).isEqualTo(" user ");
        assertThat(authenticated.getPassword()).isEqualTo("password");
        assertThat(authenticated.getJavaMailProperties())
                .containsEntry("mail.smtp.auth", "true")
                .containsEntry("mail.smtp.starttls.enable", "true")
                .containsEntry("mail.smtp.ssl.enable", "false")
                .containsEntry("mail.smtp.connectiontimeout", "3000")
                .containsEntry("mail.smtp.timeout", "4000");
        assertThat(anonymous.getJavaMailProperties()).containsEntry("mail.smtp.auth", "false");
    }

    private MailConfig testModeConfig(boolean enabled) {
        return new MailConfig(enabled, true, null, 0, null, null,
                "noreply@example.com", true, false, 5000, 10000, "http://localhost:3000");
    }

    private MailConfig realConfig(String username) {
        return new MailConfig(true, false, "smtp.example.com", 2525, username, "password",
                "from@example.com", true, false, 3000, 4000, "https://frontend.example");
    }
}
