package cn.rvport.backend.common.web;

import java.util.List;

public record PageResponse<T>(
        List<T> items,
        int page,
        int pageSize,
        long total,
        boolean hasMore
) {
    public static <T> PageResponse<T> of(List<T> items, int page, int pageSize, long total) {
        return new PageResponse<>(items, page, pageSize, total, (long) page * pageSize < total);
    }
}
