package cn.rvport.backend.mail;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.systemconfig.SystemConfigEntry;
import cn.rvport.backend.systemconfig.SystemConfigService;
import cn.rvport.backend.systemconfig.SystemConfigValueType;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class MailConfigService {

    public static final String MAIL_NAMESPACE = "mail";

    private static final String ENABLED = "enabled";
    private static final String TEST_MODE = "testMode";
    private static final String HOST = "host";
    private static final String PORT = "port";
    private static final String USERNAME = "username";
    private static final String PASSWORD = "password";
    private static final String FROM_ADDRESS = "fromAddress";
    private static final String START_TLS = "startTls";
    private static final String SSL = "ssl";
    private static final String CONNECTION_TIMEOUT = "connectionTimeoutMillis";
    private static final String READ_TIMEOUT = "readTimeoutMillis";
    private static final String FRONTEND_BASE_URL = "frontendBaseUrl";

    private final SystemConfigService systemConfigService;

    public MailConfigService(SystemConfigService systemConfigService) {
        this.systemConfigService = systemConfigService;
    }

    public MailSettingsResponse currentSettings() {
        Map<String, SystemConfigEntry> entries = systemConfigService.findNamespace(MAIL_NAMESPACE);
        return new MailSettingsResponse(
                bool(entries, ENABLED, false),
                bool(entries, TEST_MODE, true),
                value(entries, HOST),
                integer(entries, PORT, null),
                value(entries, USERNAME),
                entries.containsKey(PASSWORD),
                value(entries, FROM_ADDRESS),
                bool(entries, START_TLS, true),
                bool(entries, SSL, false),
                integer(entries, CONNECTION_TIMEOUT, 5000),
                integer(entries, READ_TIMEOUT, 10000),
                value(entries, FRONTEND_BASE_URL)
        );
    }

    public MailConfig currentConfig() {
        MailSettingsResponse settings = currentSettings();
        return new MailConfig(
                settings.enabled(),
                settings.testMode(),
                settings.host(),
                settings.port() == null ? 0 : settings.port(),
                settings.username(),
                systemConfigService.plainValue(MAIL_NAMESPACE, PASSWORD).orElse(null),
                settings.fromAddress(),
                settings.startTls(),
                settings.ssl(),
                settings.connectionTimeoutMillis(),
                settings.readTimeoutMillis(),
                settings.frontendBaseUrl()
        );
    }

    @Transactional
    public MailSettingsResponse update(MailSettingsRequest request, UUID actorUserId) {
        saveBoolean(ENABLED, request.enabled(), actorUserId);
        saveBoolean(TEST_MODE, request.testMode(), actorUserId);
        saveString(HOST, blankToNull(request.host()), actorUserId);
        saveInteger(PORT, request.port(), actorUserId);
        saveString(USERNAME, blankToNull(request.username()), actorUserId);
        systemConfigService.saveSecret(MAIL_NAMESPACE, PASSWORD, request.password(), actorUserId);
        saveString(FROM_ADDRESS, blankToNull(request.fromAddress()), actorUserId);
        saveBoolean(START_TLS, request.startTls(), actorUserId);
        saveBoolean(SSL, request.ssl(), actorUserId);
        saveInteger(CONNECTION_TIMEOUT, request.connectionTimeoutMillis(), actorUserId);
        saveInteger(READ_TIMEOUT, request.readTimeoutMillis(), actorUserId);
        saveString(FRONTEND_BASE_URL, normalizeFrontendUrl(request.frontendBaseUrl()), actorUserId);
        return currentSettings();
    }

    public void validateSendable(MailConfig config) {
        if (!config.enabled()) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "MAIL_DISABLED", "邮箱发送未启用");
        }
        if (config.testMode()) {
            return;
        }
        if (isBlank(config.host()) || config.port() <= 0 || isBlank(config.fromAddress())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "MAIL_CONFIG_INCOMPLETE", "邮箱服务器配置不完整");
        }
    }

    private void saveString(String key, String value, UUID actorUserId) {
        systemConfigService.savePlain(MAIL_NAMESPACE, key, value, SystemConfigValueType.STRING, actorUserId);
    }

    private void saveInteger(String key, Integer value, UUID actorUserId) {
        systemConfigService.savePlain(MAIL_NAMESPACE, key, value == null ? null : value.toString(), SystemConfigValueType.NUMBER, actorUserId);
    }

    private void saveBoolean(String key, Boolean value, UUID actorUserId) {
        systemConfigService.savePlain(MAIL_NAMESPACE, key, value == null ? null : value.toString(), SystemConfigValueType.BOOLEAN, actorUserId);
    }

    private String value(Map<String, SystemConfigEntry> entries, String key) {
        SystemConfigEntry entry = entries.get(key);
        return entry == null || entry.encrypted() ? null : entry.value();
    }

    private boolean bool(Map<String, SystemConfigEntry> entries, String key, boolean fallback) {
        String value = value(entries, key);
        return value == null ? fallback : Boolean.parseBoolean(value);
    }

    private Integer integer(Map<String, SystemConfigEntry> entries, String key, Integer fallback) {
        String value = value(entries, key);
        if (value == null || value.isBlank()) {
            return fallback;
        }
        try {
            return Integer.parseInt(value);
        } catch (NumberFormatException ex) {
            return fallback;
        }
    }

    private String normalizeFrontendUrl(String value) {
        String trimmed = blankToNull(value);
        if (trimmed == null) {
            return null;
        }
        return trimmed.endsWith("/") ? trimmed.substring(0, trimmed.length() - 1) : trimmed;
    }

    private String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }

    private boolean isBlank(String value) {
        return value == null || value.isBlank();
    }
}
