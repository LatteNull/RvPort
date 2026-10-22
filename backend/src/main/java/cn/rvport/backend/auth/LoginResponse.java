package cn.rvport.backend.auth;

import cn.rvport.backend.user.UserResponse;

public record LoginResponse(
        UserResponse user
) {
}
