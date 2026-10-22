package cn.rvport.backend.mail;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.mockito.Mockito.times;
import static org.mockito.ArgumentMatchers.eq;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.systemconfig.SystemConfigEntry;
import cn.rvport.backend.systemconfig.SystemConfigService;
import cn.rvport.backend.systemconfig.SystemConfigValueType;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class MailConfigServiceTests {

    @Mock
    private SystemConfigService systemConfigService;

    @Test
    void returnsMaskedSettingsAndSavesWhitelistedFields() {
        UUID actorId = UUID.randomUUID();
        MailConfigService service = new MailConfigService(systemConfigService);
        when(systemConfigService.findNamespace("mail")).thenReturn(Map.of(
                "enabled", entry("enabled", "true", SystemConfigValueType.BOOLEAN, false),
                "password", entry("password", "cipher", SystemConfigValueType.SECRET, true),
                "port", entry("port", "2525", SystemConfigValueType.NUMBER, false)
        ));

        MailSettingsResponse before = service.currentSettings();
        MailSettingsResponse after = service.update(new MailSettingsRequest(
                true, true, "smtp.example.com", 2525, "user", "Secret123",
                "noreply@example.com", true, false, 5000, 10000, "http://localhost:5173/"), actorId);

        assertThat(before.passwordConfigured()).isTrue();
        assertThat(after.port()).isEqualTo(2525);
        verify(systemConfigService).saveSecret("mail", "password", "Secret123", actorId);
        verify(systemConfigService).savePlain("mail", "frontendBaseUrl", "http://localhost:5173", SystemConfigValueType.STRING, actorId);
    }

    @Test
    void validateSendableAllowsTestModeButRejectsIncompleteRealConfig() {
        MailConfigService service = new MailConfigService(systemConfigService);

        service.validateSendable(new MailConfig(true, true, null, 0, null, null, null, true, false, 5000, 10000, null));

        assertThatThrownBy(() -> service.validateSendable(new MailConfig(true, false, null, 0, null, null, null, true, false, 5000, 10000, null)))
                .isInstanceOf(ApiException.class)
                .hasMessage("邮箱服务器配置不完整");
    }

    @Test
    void currentSettingsUsesDefaultsAndHidesEncryptedOrMalformedValues() {
        MailConfigService service = new MailConfigService(systemConfigService);
        when(systemConfigService.findNamespace("mail")).thenReturn(Map.of());
        MailSettingsResponse defaults = service.currentSettings();
        assertThat(defaults.enabled()).isFalse();
        assertThat(defaults.testMode()).isTrue();
        assertThat(defaults.port()).isNull();
        assertThat(defaults.connectionTimeoutMillis()).isEqualTo(5000);
        assertThat(defaults.readTimeoutMillis()).isEqualTo(10000);

        when(systemConfigService.findNamespace("mail")).thenReturn(Map.of(
                "host", entry("host", "secret-host", SystemConfigValueType.SECRET, true),
                "port", entry("port", "not-a-number", SystemConfigValueType.NUMBER, false),
                "connectionTimeoutMillis", entry("connectionTimeoutMillis", " ", SystemConfigValueType.NUMBER, false),
                "testMode", entry("testMode", "false", SystemConfigValueType.BOOLEAN, false),
                "fromAddress", entry("fromAddress", "sender@example.com", SystemConfigValueType.STRING, false)
        ));
        MailSettingsResponse malformed = service.currentSettings();
        assertThat(malformed.host()).isNull();
        assertThat(malformed.port()).isNull();
        assertThat(malformed.connectionTimeoutMillis()).isEqualTo(5000);
        assertThat(malformed.testMode()).isFalse();
        assertThat(malformed.fromAddress()).isEqualTo("sender@example.com");
    }

    @Test
    void currentConfigLoadsPlainSecretAndNormalizesMissingPort() {
        MailConfigService service = new MailConfigService(systemConfigService);
        when(systemConfigService.findNamespace("mail")).thenReturn(Map.of(
                "enabled", entry("enabled", "true", SystemConfigValueType.BOOLEAN, false),
                "password", entry("password", "cipher", SystemConfigValueType.SECRET, true)
        ));
        when(systemConfigService.plainValue("mail", "password")).thenReturn(java.util.Optional.of("plain-secret"));

        MailConfig config = service.currentConfig();
        assertThat(config.port()).isZero();
        assertThat(config.password()).isEqualTo("plain-secret");
    }

    @Test
    void updatePersistsNullValuesAndBlankFrontendUrl() {
        MailConfigService service = new MailConfigService(systemConfigService);
        UUID actor = UUID.randomUUID();
        when(systemConfigService.findNamespace("mail")).thenReturn(Map.of());

        MailSettingsResponse response = service.update(new MailSettingsRequest(
                null, null, null, null, " ", null, " ", null, null, null, null, " "), actor);

        assertThat(response.enabled()).isFalse();
        verify(systemConfigService, times(4)).savePlain(eq("mail"), org.mockito.ArgumentMatchers.anyString(),
                org.mockito.ArgumentMatchers.isNull(), org.mockito.ArgumentMatchers.eq(SystemConfigValueType.BOOLEAN), eq(actor));
        verify(systemConfigService, times(3)).savePlain(eq("mail"), org.mockito.ArgumentMatchers.anyString(),
                org.mockito.ArgumentMatchers.isNull(), org.mockito.ArgumentMatchers.eq(SystemConfigValueType.NUMBER), eq(actor));
        verify(systemConfigService).savePlain("mail", "frontendBaseUrl", null, SystemConfigValueType.STRING, actor);
    }

    @Test
    void validateSendableCoversDisabledAndEveryIncompleteFieldAndAcceptsCompleteConfig() {
        MailConfigService service = new MailConfigService(systemConfigService);
        assertThatThrownBy(() -> service.validateSendable(new MailConfig(false, true, null, 0, null, null,
                null, false, false, 1, 1, null))).isInstanceOf(ApiException.class).hasMessage("邮箱发送未启用");

        service.validateSendable(new MailConfig(true, false, "smtp.example.com", 25, null, null,
                "sender@example.com", false, false, 1, 1, null));
        for (MailConfig invalid : java.util.List.of(
                new MailConfig(true, false, " ", 25, null, null, "sender@example.com", false, false, 1, 1, null),
                new MailConfig(true, false, "smtp.example.com", 0, null, null, "sender@example.com", false, false, 1, 1, null),
                new MailConfig(true, false, "smtp.example.com", 25, null, null, " ", false, false, 1, 1, null)
        )) {
            assertThatThrownBy(() -> service.validateSendable(invalid)).isInstanceOf(ApiException.class);
        }
    }

    private SystemConfigEntry entry(String key, String value, SystemConfigValueType type, boolean encrypted) {
        return new SystemConfigEntry("mail", key, value, type, encrypted);
    }
}
