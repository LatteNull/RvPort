package cn.rvport.backend.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "rvport.object-storage")
public record ObjectStorageProperties(
        boolean enabled,
        String endpoint,
        String region,
        String bucket,
        String accessKey,
        String secretKey,
        boolean pathStyle,
        boolean autoCreateBucket
) {
}
