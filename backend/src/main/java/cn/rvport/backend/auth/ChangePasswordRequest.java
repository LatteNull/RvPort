package cn.rvport.backend.auth;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record ChangePasswordRequest(
        @NotBlank @Size(max = 16) String currentPassword,
        @NotBlank @Size(max = 16) String newPassword
) {
}
