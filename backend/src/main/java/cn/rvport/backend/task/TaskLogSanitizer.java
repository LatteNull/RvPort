package cn.rvport.backend.task;

import java.util.regex.Pattern;

final class TaskLogSanitizer {

    static final int MAX_EXCERPT_LENGTH = 500;

    private static final Pattern SENSITIVE_PAIR = Pattern.compile(
            "(?i)(\"?(?:password|token|privateKey|private_key|passphrase|secret)\"?\\s*[=:]\\s*)(\"?)[^\\s,;\\]}]+(\"?)"
    );

    private TaskLogSanitizer() {
    }

    static String safeExcerpt(String content) {
        if (content == null || content.isBlank()) {
            return "";
        }
        String masked = safeContent(content.replace('\r', ' ').replace('\n', ' ').trim());
        if (masked.length() <= MAX_EXCERPT_LENGTH) {
            return masked;
        }
        return masked.substring(0, MAX_EXCERPT_LENGTH);
    }

    static String safeContent(String content) {
        if (content == null || content.isEmpty()) {
            return "";
        }
        return SENSITIVE_PAIR.matcher(content).replaceAll("$1$2****$3");
    }
}
