package cn.rvport.backend.useraction;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.jooq.tables.records.UserActionTokensRecord;
import cn.rvport.backend.testfixture.JooqMockDatabase;
import java.sql.SQLException;
import java.time.OffsetDateTime;
import java.util.UUID;
import org.jooq.JSONB;
import org.junit.jupiter.api.Test;

class UserActionTokenRepositoryTests {
    private static final UUID ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID USER_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final UUID ACTOR_ID = UUID.fromString("30000000-0000-0000-0000-000000000001");
    private static final OffsetDateTime NOW = OffsetDateTime.parse("2026-09-11T10:00:00Z");

    @Test
    void createsConsumesAndFindsOnlyOpenUnexpiredTokens() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            UserActionTokenRepository repository = new UserActionTokenRepository(database.dsl());
            database.enqueueRecord(record()).enqueueRows(2).enqueueRecord(record()).enqueueRows(1).enqueueRows(0);
            assertThat(repository.create(USER_ID, UserActionTokenType.INVITATION, "hash", NOW.plusDays(1), ACTOR_ID).tokenHash()).isEqualTo("hash");
            repository.consumeOpenTokens(USER_ID, UserActionTokenType.INVITATION);
            assertThat(repository.findOpenByHash("hash", UserActionTokenType.INVITATION, NOW)).isPresent();
            assertThat(repository.consume(ID)).isTrue();
            assertThat(repository.consume(ID)).isFalse();
            assertThat(database.executions().get(2).normalizedSql()).contains("consumed_at is null", "expires_at >");
            database.verifyComplete();
        }
    }

    @Test
    void deletesOldConsumedOrExpiredTokensAndPropagatesFailure() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            UserActionTokenRepository repository = new UserActionTokenRepository(database.dsl());
            database.enqueueRows(3);
            assertThat(repository.deleteConsumedOrExpiredBefore(NOW)).isEqualTo(3);
            assertThat(database.lastExecution().normalizedSql()).contains("consumed_at <", "or", "expires_at <");
            database.enqueueFailure(new SQLException("database unavailable"));
            assertThatThrownBy(() -> repository.findOpenByHash("hash", UserActionTokenType.INVITATION, NOW))
                    .isInstanceOf(org.jooq.exception.DataAccessException.class).hasMessageContaining("database unavailable");
            database.verifyComplete();
        }
    }

    private static UserActionTokensRecord record() {
        return new UserActionTokensRecord(ID, USER_ID, UserActionTokenType.INVITATION.name(), "hash", NOW.plusDays(1),
                null, ACTOR_ID, NOW, JSONB.valueOf("{}"));
    }
}
