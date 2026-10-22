package cn.rvport.backend.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "rvport.security.credentials")
public record CredentialCryptoProperties(
        String masterKey,
        String keyId
) {
}
