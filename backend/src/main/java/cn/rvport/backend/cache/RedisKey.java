package cn.rvport.backend.cache;

import java.util.List;

public record RedisKey(
        String domain,
        String purpose,
        List<String> parts
) {
    public RedisKey {
        if (isBlank(domain)) {
            throw new IllegalArgumentException("Redis key domain must not be blank.");
        }
        if (isBlank(purpose)) {
            throw new IllegalArgumentException("Redis key purpose must not be blank.");
        }
        parts = parts == null ? List.of() : List.copyOf(parts);
        parts.forEach(part -> {
            if (isBlank(part) || part.contains(":")) {
                throw new IllegalArgumentException("Redis key parts must be non-blank and must not contain ':'.");
            }
        });
    }

    public static RedisKey of(String domain, String purpose, String... parts) {
        return new RedisKey(domain, purpose, List.of(parts));
    }

    private static boolean isBlank(String value) {
        return value == null || value.isBlank();
    }
}
