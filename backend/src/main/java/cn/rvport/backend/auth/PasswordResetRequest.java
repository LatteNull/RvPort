package cn.rvport.backend.auth;

import jakarta.validation.constraints.NotBlank;

public record PasswordResetRequest(
        @NotBlank String identifier
) {
}
