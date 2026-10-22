package cn.rvport.backend.user;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.OffsetDateTime;
import java.util.UUID;

public record UserResponse(
        UUID id,
        String username,
        String displayName,
        String email,
        @JsonProperty("isSuperAdmin")
        boolean superAdmin,
        boolean mustChangePassword,
        UserStatus status,
        OffsetDateTime lastLoginAt,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
    public static UserResponse from(UserView user) {
        return new UserResponse(
                user.id(),
                user.username(),
                user.displayName(),
                user.email(),
                user.superAdmin(),
                user.mustChangePassword(),
                user.status(),
                user.lastLoginAt(),
                user.createdAt(),
                user.updatedAt()
        );
    }
}
