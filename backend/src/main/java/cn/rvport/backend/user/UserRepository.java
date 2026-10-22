package cn.rvport.backend.user;

import static cn.rvport.backend.jooq.tables.Users.USERS;

import cn.rvport.backend.jooq.tables.records.UsersRecord;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.jooq.Condition;
import org.jooq.DSLContext;
import org.jooq.impl.DSL;
import org.springframework.stereotype.Repository;

@Repository
public class UserRepository {

    private final DSLContext dsl;

    public UserRepository(DSLContext dsl) {
        this.dsl = dsl;
    }

    public Optional<UserWithPassword> findByUsernameWithPassword(String username) {
        return dsl.selectFrom(USERS)
                .where(USERS.USERNAME.eq(username))
                .fetchOptional()
                .map(this::withPassword);
    }

    public Optional<UserView> findByUsernameOrEmail(String identifier) {
        if (identifier == null || identifier.isBlank()) {
            return Optional.empty();
        }
        String normalized = identifier.trim().toLowerCase();
        return dsl.selectFrom(USERS)
                .where(DSL.lower(USERS.USERNAME).eq(normalized)
                        .or(DSL.lower(USERS.EMAIL).eq(normalized)))
                .fetchOptional()
                .map(UserView::from);
    }

    public Optional<UserView> findById(UUID userId) {
        return dsl.selectFrom(USERS)
                .where(USERS.ID.eq(userId))
                .fetchOptional()
                .map(UserView::from);
    }

    public Optional<UserWithPassword> findByIdWithPassword(UUID userId) {
        return dsl.selectFrom(USERS)
                .where(USERS.ID.eq(userId))
                .fetchOptional()
                .map(this::withPassword);
    }

    public boolean existsByUsername(String username) {
        return dsl.fetchExists(USERS, USERS.USERNAME.eq(username));
    }

    public boolean existsByEmail(String email) {
        if (email == null || email.isBlank()) {
            return false;
        }
        return dsl.fetchExists(USERS, USERS.EMAIL.eq(email));
    }

    public boolean existsByEmailExcludingId(String email, UUID userId) {
        if (email == null || email.isBlank()) {
            return false;
        }
        return dsl.fetchExists(USERS, USERS.EMAIL.eq(email).and(USERS.ID.ne(userId)));
    }

    public long count(UserStatus status, String keyword) {
        return dsl.selectCount()
                .from(USERS)
                .where(filter(status, keyword))
                .fetchOne(0, long.class);
    }

    public List<UserView> list(UserStatus status, String keyword, int page, int pageSize) {
        return dsl.selectFrom(USERS)
                .where(filter(status, keyword))
                .orderBy(USERS.CREATED_AT.desc(), USERS.USERNAME.asc())
                .limit(pageSize)
                .offset((page - 1) * pageSize)
                .fetch(UserView::from);
    }

    public UserView create(
            String username,
            String displayName,
            String email,
            String passwordHash,
            boolean mustChangePassword,
            UserStatus status
    ) {
        UsersRecord record = dsl.insertInto(USERS)
                .set(USERS.USERNAME, username)
                .set(USERS.DISPLAY_NAME, displayName)
                .set(USERS.EMAIL, normalizeEmail(email))
                .set(USERS.PASSWORD_HASH, passwordHash)
                .set(USERS.IS_SUPER_ADMIN, false)
                .set(USERS.MUST_CHANGE_PASSWORD, mustChangePassword)
                .set(USERS.STATUS, status.name())
                .returning()
                .fetchOne();
        return UserView.from(record);
    }

    public UserView update(UUID userId, String displayName, String email, UserStatus status) {
        UsersRecord record = dsl.update(USERS)
                .set(USERS.DISPLAY_NAME, displayName)
                .set(USERS.EMAIL, normalizeEmail(email))
                .set(USERS.STATUS, status.name())
                .set(USERS.UPDATED_AT, OffsetDateTime.now())
                .where(USERS.ID.eq(userId))
                .returning()
                .fetchOne();
        return record == null ? null : UserView.from(record);
    }

    public UserView updateProfile(UUID userId, String displayName) {
        UsersRecord record = dsl.update(USERS)
                .set(USERS.DISPLAY_NAME, displayName)
                .set(USERS.UPDATED_AT, OffsetDateTime.now())
                .where(USERS.ID.eq(userId))
                .returning()
                .fetchOne();
        return record == null ? null : UserView.from(record);
    }

    public UserView resetPassword(UUID userId, String passwordHash, boolean mustChangePassword) {
        UsersRecord record = dsl.update(USERS)
                .set(USERS.PASSWORD_HASH, passwordHash)
                .set(USERS.MUST_CHANGE_PASSWORD, mustChangePassword)
                .set(USERS.UPDATED_AT, OffsetDateTime.now())
                .where(USERS.ID.eq(userId))
                .returning()
                .fetchOne();
        return record == null ? null : UserView.from(record);
    }

    public UserView changeOwnPassword(UUID userId, String passwordHash) {
        UsersRecord record = dsl.update(USERS)
                .set(USERS.PASSWORD_HASH, passwordHash)
                .set(USERS.MUST_CHANGE_PASSWORD, false)
                .set(USERS.UPDATED_AT, OffsetDateTime.now())
                .where(USERS.ID.eq(userId))
                .returning()
                .fetchOne();
        return record == null ? null : UserView.from(record);
    }

    public void updateLastLoginAt(UUID userId) {
        dsl.update(USERS)
                .set(USERS.LAST_LOGIN_AT, OffsetDateTime.now())
                .set(USERS.UPDATED_AT, OffsetDateTime.now())
                .where(USERS.ID.eq(userId))
                .execute();
    }

    private UserWithPassword withPassword(UsersRecord record) {
        return new UserWithPassword(UserView.from(record), record.getPasswordHash());
    }

    private Condition filter(UserStatus status, String keyword) {
        Condition condition = DSL.trueCondition();
        if (status != null) {
            condition = condition.and(USERS.STATUS.eq(status.name()));
        }
        if (keyword != null && !keyword.isBlank()) {
            String like = "%" + keyword.trim().toLowerCase() + "%";
            condition = condition.and(
                    DSL.lower(USERS.USERNAME).like(like)
                            .or(DSL.lower(USERS.DISPLAY_NAME).like(like))
                            .or(DSL.lower(USERS.EMAIL).like(like))
            );
        }
        return condition;
    }

    private String normalizeEmail(String email) {
        return email == null || email.isBlank() ? null : email.trim();
    }
}
