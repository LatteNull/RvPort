package cn.rvport.backend.auth;

import com.fasterxml.jackson.annotation.JsonProperty;

public record UpdateProfileRequest(
        String displayName,
        String username,
        String email,
        @JsonProperty("isSuperAdmin") Boolean superAdmin,
        Object status,
        Object mustChangePassword,
        Object passwordHash
) {
}
