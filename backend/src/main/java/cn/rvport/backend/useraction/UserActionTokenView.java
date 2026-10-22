package cn.rvport.backend.useraction;

import cn.rvport.backend.jooq.tables.records.UserActionTokensRecord;
import java.time.OffsetDateTime;
import java.util.UUID;

public record UserActionTokenView(
        UUID id,
        UUID userId,
        UserActionTokenType tokenType,
        String tokenHash,
        OffsetDateTime expiresAt,
        OffsetDateTime consumedAt,
        UUID createdBy,
        OffsetDateTime createdAt
) {
    public static UserActionTokenView from(UserActionTokensRecord record) {
        return new UserActionTokenView(
                record.getId(),
                record.getUserId(),
                UserActionTokenType.valueOf(record.getTokenType()),
                record.getTokenHash(),
                record.getExpiresAt(),
                record.getConsumedAt(),
                record.getCreatedBy(),
                record.getCreatedAt()
        );
    }
}
