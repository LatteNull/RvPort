package cn.rvport.backend.user;

public record UserWithPassword(
        UserView user,
        String passwordHash
) {
}
