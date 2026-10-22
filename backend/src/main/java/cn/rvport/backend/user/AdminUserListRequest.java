package cn.rvport.backend.user;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

public record AdminUserListRequest(
        @Min(1) Integer page,
        @Min(1) @Max(100) Integer pageSize,
        UserStatus status,
        String keyword
) {
    public int normalizedPage() {
        return page == null ? 1 : page;
    }

    public int normalizedPageSize() {
        return pageSize == null ? 20 : pageSize;
    }
}
