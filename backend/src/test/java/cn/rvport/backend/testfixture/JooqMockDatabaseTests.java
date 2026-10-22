package cn.rvport.backend.testfixture;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.sql.SQLException;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.UUID;
import org.jooq.Field;
import org.jooq.JSONB;
import org.jooq.Record;
import org.jooq.Result;
import org.jooq.exception.DataAccessException;
import org.jooq.impl.DSL;
import org.junit.jupiter.api.Test;

class JooqMockDatabaseTests {

    private static final Field<UUID> ID = DSL.field("id", UUID.class);
    private static final Field<String> NAME = DSL.field("name", String.class);

    @Test
    void capturesSqlBindingsAndMapsTypedResults() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            UUID id = UUID.randomUUID();
            OffsetDateTime createdAt = OffsetDateTime.of(2026, 9, 11, 12, 0, 0, 0, ZoneOffset.UTC);
            Field<JSONB> payload = DSL.field("payload", JSONB.class);
            Field<OffsetDateTime> timestamp = DSL.field("created_at", OffsetDateTime.class);
            Result<Record> result = database.result(
                    new Field<?>[] {ID, NAME, payload, timestamp},
                    new Object[] {id, "project", JSONB.valueOf("{\"enabled\":true}"), createdAt}
            );
            database.enqueueResult(result);

            Record record = database.dsl().select(ID, NAME, payload, timestamp)
                    .from("projects")
                    .where(ID.eq(id))
                    .fetchOne();

            assertThat(record).isNotNull();
            assertThat(record.get(ID)).isEqualTo(id);
            assertThat(record.get(payload).data()).contains("enabled");
            assertThat(record.get(timestamp)).isEqualTo(createdAt);
            assertThat(database.lastExecution().sql())
                    .contains("from projects")
                    .contains("where id = cast(? as uuid)");
            assertThat(database.lastExecution().bindings()).containsExactly(id);
            database.verifyComplete();
        }
    }

    @Test
    void supportsEmptyReturningMultipleResultsAndBatch() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            database.enqueueResult(database.result(new Field<?>[] {ID}));
            assertThat(database.dsl().select(ID).from("projects").fetch()).isEmpty();

            Result<Record> returned = database.result(
                    new Field<?>[] {ID, NAME},
                    new Object[] {UUID.randomUUID(), "created"}
            );
            database.enqueueResult(returned);
            assertThat(database.dsl().insertInto(DSL.table("projects"))
                    .columns(ID, NAME)
                    .values(returned.getFirst().get(ID), "created")
                    .returning(ID, NAME)
                    .fetchOne(NAME)).isEqualTo("created");

            database.enqueue(new org.jooq.tools.jdbc.MockResult(1), new org.jooq.tools.jdbc.MockResult(2));
            database.dsl().fetchMany("select 1; select 2");

            database.enqueueRows(2);
            database.dsl().batch(
                    database.dsl().insertInto(DSL.table("projects")).columns(NAME).values("one"),
                    database.dsl().insertInto(DSL.table("projects")).columns(NAME).values("two")
            ).execute();

            assertThat(database.lastExecution().batch()).isTrue();
            assertThat(database.lastExecution().batchSql()).hasSize(2);
            database.verifyComplete();
        }
    }

    @Test
    void rejectsInvalidFixturesAndPropagatesDatabaseFailures() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            assertThatThrownBy(() -> database.result(
                    new Field<?>[] {ID, NAME}, new Object[] {UUID.randomUUID()}))
                    .isInstanceOf(IllegalArgumentException.class)
                    .hasMessageContaining("字段数量");
            assertThatThrownBy(database::lastExecution)
                    .isInstanceOf(IllegalStateException.class);
            assertThatThrownBy(() -> database.dsl().selectOne().fetch())
                    .isInstanceOf(DataAccessException.class)
                    .hasMessageContaining("测试未配置 SQL 响应");

            database.enqueueFailure(new SQLException("database unavailable"));
            assertThatThrownBy(() -> database.dsl().selectOne().fetch())
                    .isInstanceOf(DataAccessException.class)
                    .hasMessageContaining("database unavailable");

            database.enqueueRows(1);
            assertThatThrownBy(database::verifyComplete)
                    .isInstanceOf(AssertionError.class)
                    .hasMessageContaining("未消费");
        }
    }
}
