package cn.rvport.backend.migration;

import java.util.Locale;
import java.util.Set;

public final class MigrationInputRiskPolicy {

    private static final Set<String> KNOWN_LEVELS = Set.of("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO", "COMMENT");

    private MigrationInputRiskPolicy() {
    }

    public static String normalizeRiskToken(String value) {
        if (value == null || value.isBlank()) {
            return "INFO";
        }
        String token = value.trim();
        int slash = token.indexOf('/');
        if (slash >= 0) {
            token = token.substring(0, slash);
        }
        token = token.trim().toUpperCase(Locale.ROOT);
        return KNOWN_LEVELS.contains(token) ? token : "INFO";
    }

    public static boolean isKnownRiskToken(String value) {
        if (value == null || value.isBlank()) {
            return false;
        }
        String token = value.trim();
        int slash = token.indexOf('/');
        if (slash >= 0) {
            token = token.substring(0, slash);
        }
        return KNOWN_LEVELS.contains(token.trim().toUpperCase(Locale.ROOT));
    }

    public static MigrationInputStatus defaultStatus(String detectedLevel) {
        return "LOW".equals(normalizeRiskToken(detectedLevel))
                ? MigrationInputStatus.CANDIDATE
                : MigrationInputStatus.CONFIRMED;
    }

    public static String normalizedDetectedLevel(String riskLevel) {
        return normalizeRiskToken(riskLevel);
    }

    public static String normalizedDetectedLevel(String riskLevel, String status) {
        return normalizeRiskToken(riskLevel) + "/" + defaultText(status, "UNKNOWN");
    }

    private static String defaultText(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value.trim().toUpperCase(Locale.ROOT);
    }
}
