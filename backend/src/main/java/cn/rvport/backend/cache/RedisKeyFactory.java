package cn.rvport.backend.cache;

import java.util.ArrayList;
import java.util.List;

public class RedisKeyFactory {

    private final String namespace;

    public RedisKeyFactory(String namespace) {
        if (namespace == null || namespace.isBlank()) {
            throw new IllegalArgumentException("Redis cache namespace must not be blank.");
        }
        this.namespace = stripTrailingSeparator(namespace);
    }

    public String format(RedisKey key) {
        List<String> segments = new ArrayList<>();
        segments.add(namespace);
        segments.add(key.domain());
        segments.add(key.purpose());
        segments.addAll(key.parts());
        return String.join(":", segments);
    }

    private static String stripTrailingSeparator(String value) {
        String result = value.trim();
        while (result.endsWith(":")) {
            result = result.substring(0, result.length() - 1);
        }
        return result;
    }
}
