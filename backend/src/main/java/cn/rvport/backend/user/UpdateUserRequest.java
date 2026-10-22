package cn.rvport.backend.user;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.Email;

public record UpdateUserRequest(
        String displayName,
        @Email String email,
        UserStatus status,
        String username,
        @JsonProperty("isSuperAdmin") Boolean superAdmin,
        Boolean mustChangePassword,
        Object passwordHash,
        Object roles,
        Object permissions
) {
}
