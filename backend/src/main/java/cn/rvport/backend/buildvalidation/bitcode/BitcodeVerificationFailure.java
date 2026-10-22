package cn.rvport.backend.buildvalidation.bitcode;

import java.util.LinkedHashMap;
import java.util.Map;

/** 可写入运行摘要的脱敏 BC 校验失败。 */
public record BitcodeVerificationFailure(
        BitcodeVerificationStage stage,
        BitcodeReasonCode reasonCode,
        String schemaVersion,
        String producerVersion,
        String artifactIdentity,
        String expectedDigest,
        String actualDigest,
        boolean retryable,
        String message,
        String messageEn,
        String suggestion,
        String suggestionEn
) {
    public Map<String, Object> safeSummary() {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("stage", stage.name());
        result.put("reasonCode", reasonCode.name());
        result.put("schemaVersion", safeText(schemaVersion));
        result.put("producerVersion", safeText(producerVersion));
        result.put("artifactIdentity", shortDigest(artifactIdentity));
        result.put("expectedDigest", shortDigest(expectedDigest));
        result.put("actualDigest", shortDigest(actualDigest));
        result.put("retryable", retryable);
        result.put("message", safeText(message));
        result.put("messageEn", safeText(messageEn));
        result.put("suggestion", safeText(suggestion));
        result.put("suggestionEn", safeText(suggestionEn));
        return result;
    }

    private String shortDigest(String value) {
        if (value == null || value.isBlank()) return null;
        String normalized = value.matches("[0-9a-f]{64}") ? value.substring(0, 12) : value;
        return safeText(normalized);
    }

    private String safeText(String value) {
        if (value == null) return null;
        String normalized = value.replace('\r', ' ').replace('\n', ' ')
                .replaceAll("(?i)(?:[a-z]:)?[/\\\\][^ ]+", "<PATH>")
                .replaceAll("(?i)(?:access|secret|token|password)[_-]?key=[^ ]+", "<REDACTED>");
        return normalized.length() <= 512 ? normalized : normalized.substring(0, 512);
    }
}
