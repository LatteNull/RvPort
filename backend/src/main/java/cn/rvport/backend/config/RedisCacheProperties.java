package cn.rvport.backend.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "rvport.cache")
public record RedisCacheProperties(
        String namespace
) {
}
