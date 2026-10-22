package cn.rvport.backend.user;

import static cn.rvport.backend.jooq.tables.Users.USERS;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.jooq.tables.records.UsersRecord;
import cn.rvport.backend.testfixture.JooqMockDatabase;
import java.sql.SQLException;
import java.time.OffsetDateTime;
import java.util.UUID;
import org.jooq.Field;
import org.jooq.impl.DSL;
import org.junit.jupiter.api.Test;

class UserRepositoryTests {
    private static final UUID ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final OffsetDateTime NOW = OffsetDateTime.parse("2026-09-11T10:00:00Z");

    @Test
    void findsUsersWithAndWithoutPasswordsAndNormalizesIdentifiers() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            UserRepository repository = new UserRepository(database.dsl());
            assertThat(repository.findByUsernameOrEmail(null)).isEmpty();
            assertThat(repository.findByUsernameOrEmail(" ")).isEmpty();
            assertThat(database.executions()).isEmpty();
            database.enqueueRecord(record()).enqueueRecord(record()).enqueueRecord(record()).enqueueRecord(record());
            assertThat(repository.findByUsernameWithPassword("alice").orElseThrow().passwordHash()).isEqualTo("hash");
            assertThat(repository.findByUsernameOrEmail(" Alice@Example.COM ").orElseThrow().username()).isEqualTo("alice");
            assertThat(repository.findById(ID)).isPresent();
            assertThat(repository.findByIdWithPassword(ID)).isPresent();
            assertThat(database.executions().get(1).bindings()).contains("alice@example.com");
            database.verifyComplete();
        }
    }

    @Test
    void checksUsernameAndEmailUniquenessWithBlankShortCircuit() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            UserRepository repository = new UserRepository(database.dsl());
            database.enqueueResult(database.result(new Field<?>[]{DSL.field("exists", Boolean.class)}, new Object[]{true}))
                    .enqueueResult(database.result(new Field<?>[]{DSL.field("exists", Boolean.class)}, new Object[]{false}))
                    .enqueueResult(database.result(new Field<?>[]{DSL.field("exists", Boolean.class)}, new Object[]{true}));
            assertThat(repository.existsByUsername("alice")).isTrue();
            assertThat(repository.existsByEmail(null)).isFalse();
            assertThat(repository.existsByEmail(" ")).isFalse();
            assertThat(repository.existsByEmail("alice@example.com")).isFalse();
            assertThat(repository.existsByEmailExcludingId(" ", ID)).isFalse();
            assertThat(repository.existsByEmailExcludingId("alice@example.com", ID)).isTrue();
            assertThat(database.executions()).hasSize(3);
            assertThat(database.executions().get(2).normalizedSql()).contains("id <>");
            database.verifyComplete();
        }
    }

    @Test
    void filtersCountsAndPaginatesUsersByStatusAndKeyword() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            UserRepository repository = new UserRepository(database.dsl());
            database.enqueueResult(database.result(new Field<?>[]{DSL.count()}, new Object[]{1L})).enqueueRecord(record());
            assertThat(repository.count(UserStatus.ACTIVE, " Alice ")).isEqualTo(1);
            assertThat(repository.list(UserStatus.ACTIVE, " Alice ", 2, 5)).hasSize(1);
            assertThat(database.executions().getFirst().normalizedSql()).contains("status =", "lower", "like");
            assertThat(database.executions().get(1).normalizedSql()).contains("created_at desc", "username asc", "offset ? rows");
            database.verifyComplete();
        }
    }

    @Test
    void createsUserAndNormalizesBlankOrTrimmedEmail() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            UserRepository repository = new UserRepository(database.dsl());
            database.enqueueRecord(record()).enqueueRecord(record());
            assertThat(repository.create("alice", "Alice", " alice@example.com ", "hash", true, UserStatus.ACTIVE).email())
                    .isEqualTo("alice@example.com");
            repository.create("bob", "Bob", " ", "hash", false, UserStatus.DISABLED);
            assertThat(database.executions().getFirst().bindings()).contains("alice@example.com", false, true);
            assertThat(database.executions().get(1).bindings()).containsNull();
            database.verifyComplete();
        }
    }

    @Test
    void updatesProfileAccountAndPasswordStatesIncludingMissingRows() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            UserRepository repository = new UserRepository(database.dsl());
            database.enqueueRecord(record()).enqueueResult(database.result(USERS.fields()))
                    .enqueueRecord(record()).enqueueResult(database.result(USERS.fields()))
                    .enqueueRecord(record()).enqueueResult(database.result(USERS.fields()))
                    .enqueueRecord(record()).enqueueResult(database.result(USERS.fields()));
            assertThat(repository.update(ID, "Alice 2", " updated@example.com ", UserStatus.DISABLED)).isNotNull();
            assertThat(repository.update(ID, "Alice 2", null, UserStatus.ACTIVE)).isNull();
            assertThat(repository.updateProfile(ID, "Alice 3")).isNotNull();
            assertThat(repository.updateProfile(ID, "Alice 3")).isNull();
            assertThat(repository.resetPassword(ID, "new", true)).isNotNull();
            assertThat(repository.resetPassword(ID, "new", false)).isNull();
            assertThat(repository.changeOwnPassword(ID, "own")).isNotNull();
            assertThat(repository.changeOwnPassword(ID, "own")).isNull();
            assertThat(database.executions().get(6).bindings()).contains(false);
            database.verifyComplete();
        }
    }

    @Test
    void updatesLastLoginAndPropagatesDatabaseFailure() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            UserRepository repository = new UserRepository(database.dsl());
            database.enqueueRows(1);
            repository.updateLastLoginAt(ID);
            assertThat(database.lastExecution().normalizedSql()).contains("last_login_at", "updated_at");
            database.enqueueFailure(new SQLException("database unavailable"));
            assertThatThrownBy(() -> repository.findById(ID)).isInstanceOf(org.jooq.exception.DataAccessException.class)
                    .hasMessageContaining("database unavailable");
            database.verifyComplete();
        }
    }

    @Test
    void mapsNullBooleanFlagsToFalse() throws Exception {
        try (JooqMockDatabase database = new JooqMockDatabase()) {
            UserRepository repository = new UserRepository(database.dsl());
            UsersRecord record = record();
            record.setIsSuperAdmin(null);
            record.setMustChangePassword(null);
            database.enqueueRecord(record);
            assertThat(repository.findById(ID).orElseThrow())
                    .satisfies(user -> {
                        assertThat(user.superAdmin()).isFalse();
                        assertThat(user.mustChangePassword()).isFalse();
                    });
            database.verifyComplete();
        }
    }

    private static UsersRecord record() {
        return new UsersRecord(ID, "alice", "Alice", "alice@example.com", "hash", true, false,
                UserStatus.ACTIVE.name(), NOW, NOW, NOW);
    }
}
