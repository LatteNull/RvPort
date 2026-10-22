package cn.rvport.backend.user;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record ResetPasswordRequest(
        @NotBlank @Size(max = 16) String newPassword,
        Boolean mustChangePassword
) {
}
