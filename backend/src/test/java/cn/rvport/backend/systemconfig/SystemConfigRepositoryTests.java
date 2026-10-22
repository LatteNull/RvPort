package cn.rvport.backend.systemconfig;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.jooq.tables.records.SystemConfigsRecord;
import cn.rvport.backend.testfixture.JooqMockDatabase;
import java.sql.SQLException;
import java.time.OffsetDateTime;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class SystemConfigRepositoryTests {
    private static final UUID ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID USER_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final OffsetDateTime NOW = OffsetDateTime.parse("2026-09-11T10:00:00Z");

    @Test
    void findsNamespaceAndSingleEntriesIncludingNullEncryptedFlag() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            SystemConfigRepository repository = new SystemConfigRepository(database.dsl());
            database.enqueueRecord(record(null)).enqueueRecord(record(true));
            assertThat(repository.findNamespace("mail")).containsKey("host")
                    .extractingByKey("host").extracting(SystemConfigEntry::encrypted).isEqualTo(false);
            assertThat(repository.find("mail", "host").orElseThrow().encrypted()).isTrue();
            assertThat(database.executions().getFirst().normalizedSql()).contains("config_key asc");
            database.verifyComplete();
        }
    }

    @Test
    void upsertsDeletesAndPropagatesDatabaseFailure() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            SystemConfigRepository repository = new SystemConfigRepository(database.dsl());
            database.enqueueRows(1).enqueueRows(1);
            repository.upsert("mail", "host", "smtp.example", SystemConfigValueType.STRING, false, USER_ID);
            repository.delete("mail", "host");
            assertThat(database.executions().getFirst().normalizedSql()).contains("on conflict", "do update");
            assertThat(database.executions().get(1).normalizedSql()).contains("namespace =", "config_key =");
            database.enqueueFailure(new SQLException("database unavailable"));
            assertThatThrownBy(() -> repository.find("mail", "host")).isInstanceOf(org.jooq.exception.DataAccessException.class)
                    .hasMessageContaining("database unavailable");
            database.verifyComplete();
        }
    }

    private static SystemConfigsRecord record(Boolean encrypted) {
        return new SystemConfigsRecord(ID, "mail", "host", "smtp.example", SystemConfigValueType.STRING.name(),
                encrypted, null, USER_ID, NOW, NOW);
    }
}
