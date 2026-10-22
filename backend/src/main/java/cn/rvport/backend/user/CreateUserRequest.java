package cn.rvport.backend.user;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record CreateUserRequest(
        @NotBlank @Size(max = 64) String username,
        String displayName,
        @Email String email,
        Object initialPassword,
        Boolean mustChangePassword,
        UserStatus status,
        @JsonProperty("isSuperAdmin") Boolean superAdmin,
        Object passwordHash,
        Object roles,
        Object permissions
) {
}
