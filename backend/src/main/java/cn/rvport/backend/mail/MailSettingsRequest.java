package cn.rvport.backend.mail;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Size;

public record MailSettingsRequest(
        Boolean enabled,
        Boolean testMode,
        @Size(max = 255) String host,
        @Min(1) @Max(65535) Integer port,
        @Size(max = 255) String username,
        String password,
        @Email String fromAddress,
        Boolean startTls,
        Boolean ssl,
        @Min(100) @Max(120000) Integer connectionTimeoutMillis,
        @Min(100) @Max(120000) Integer readTimeoutMillis,
        @Size(max = 1024) String frontendBaseUrl
) {
}
