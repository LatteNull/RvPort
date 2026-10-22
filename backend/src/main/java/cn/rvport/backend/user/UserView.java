package cn.rvport.backend.user;

import cn.rvport.backend.jooq.tables.records.UsersRecord;
import java.time.OffsetDateTime;
import java.util.UUID;

public record UserView(
        UUID id,
        String username,
        String displayName,
        String email,
        boolean superAdmin,
        boolean mustChangePassword,
        UserStatus status,
        OffsetDateTime lastLoginAt,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
    public static UserView from(UsersRecord record) {
        return new UserView(
                record.getId(),
                record.getUsername(),
                record.getDisplayName(),
                record.getEmail(),
                Boolean.TRUE.equals(record.getIsSuperAdmin()),
                Boolean.TRUE.equals(record.getMustChangePassword()),
                UserStatus.valueOf(record.getStatus()),
                record.getLastLoginAt(),
                record.getCreatedAt(),
                record.getUpdatedAt()
        );
    }
}
