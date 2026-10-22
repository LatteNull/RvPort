package cn.rvport.backend.useraction;

import static cn.rvport.backend.jooq.tables.UserActionTokens.USER_ACTION_TOKENS;

import cn.rvport.backend.jooq.tables.records.UserActionTokensRecord;
import java.time.OffsetDateTime;
import java.util.Optional;
import java.util.UUID;
import org.jooq.DSLContext;
import org.jooq.JSONB;
import org.springframework.stereotype.Repository;

@Repository
public class UserActionTokenRepository {

    private final DSLContext dsl;

    public UserActionTokenRepository(DSLContext dsl) {
        this.dsl = dsl;
    }

    public UserActionTokenView create(UUID userId, UserActionTokenType type, String tokenHash, OffsetDateTime expiresAt, UUID createdBy) {
        UserActionTokensRecord record = dsl.insertInto(USER_ACTION_TOKENS)
                .set(USER_ACTION_TOKENS.USER_ID, userId)
                .set(USER_ACTION_TOKENS.TOKEN_TYPE, type.name())
                .set(USER_ACTION_TOKENS.TOKEN_HASH, tokenHash)
                .set(USER_ACTION_TOKENS.EXPIRES_AT, expiresAt)
                .set(USER_ACTION_TOKENS.CREATED_BY, createdBy)
                .set(USER_ACTION_TOKENS.METADATA, JSONB.valueOf("{}"))
                .returning()
                .fetchOne();
        return UserActionTokenView.from(record);
    }

    public void consumeOpenTokens(UUID userId, UserActionTokenType type) {
        dsl.update(USER_ACTION_TOKENS)
                .set(USER_ACTION_TOKENS.CONSUMED_AT, OffsetDateTime.now())
                .where(USER_ACTION_TOKENS.USER_ID.eq(userId)
                        .and(USER_ACTION_TOKENS.TOKEN_TYPE.eq(type.name()))
                        .and(USER_ACTION_TOKENS.CONSUMED_AT.isNull()))
                .execute();
    }

    public Optional<UserActionTokenView> findOpenByHash(String tokenHash, UserActionTokenType type, OffsetDateTime now) {
        return dsl.selectFrom(USER_ACTION_TOKENS)
                .where(USER_ACTION_TOKENS.TOKEN_HASH.eq(tokenHash)
                        .and(USER_ACTION_TOKENS.TOKEN_TYPE.eq(type.name()))
                        .and(USER_ACTION_TOKENS.CONSUMED_AT.isNull())
                        .and(USER_ACTION_TOKENS.EXPIRES_AT.gt(now)))
                .fetchOptional()
                .map(UserActionTokenView::from);
    }

    public boolean consume(UUID tokenId) {
        return dsl.update(USER_ACTION_TOKENS)
                .set(USER_ACTION_TOKENS.CONSUMED_AT, OffsetDateTime.now())
                .where(USER_ACTION_TOKENS.ID.eq(tokenId)
                        .and(USER_ACTION_TOKENS.CONSUMED_AT.isNull()))
                .execute() == 1;
    }

    public int deleteConsumedOrExpiredBefore(OffsetDateTime cutoff) {
        return dsl.deleteFrom(USER_ACTION_TOKENS)
                .where(USER_ACTION_TOKENS.CONSUMED_AT.lt(cutoff)
                        .or(USER_ACTION_TOKENS.EXPIRES_AT.lt(cutoff)))
                .execute();
    }
}
