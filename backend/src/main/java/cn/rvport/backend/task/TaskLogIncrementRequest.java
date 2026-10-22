package cn.rvport.backend.task;

import cn.rvport.backend.common.error.ApiException;
import org.springframework.http.HttpStatus;

public record TaskLogIncrementRequest(long afterEventId, int limit) {

    static final int DEFAULT_LIMIT = 500;
    static final int MAX_LIMIT = 1000;

    public static TaskLogIncrementRequest from(String afterEventId, String limit) {
        long parsedLimit = parseLong(limit, DEFAULT_LIMIT, "TASK_LOG_EVENT_LIMIT_INVALID", "日志事件读取数量必须是正整数");
        if (parsedLimit > Integer.MAX_VALUE) {
            throw invalid("TASK_LOG_EVENT_LIMIT_INVALID", "日志事件读取数量必须在 1 到 " + MAX_LIMIT + " 之间");
        }
        return new TaskLogIncrementRequest(
                parseLong(afterEventId, 0L, "TASK_LOG_EVENT_CURSOR_INVALID", "日志事件游标必须是非负整数"),
                (int) parsedLimit
        ).validated();
    }

    private TaskLogIncrementRequest validated() {
        if (limit < 1 || limit > MAX_LIMIT) {
            throw invalid("TASK_LOG_EVENT_LIMIT_INVALID", "日志事件读取数量必须在 1 到 " + MAX_LIMIT + " 之间");
        }
        return this;
    }

    static long parseCursor(String value) {
        return parseLong(value, 0L, "TASK_LOG_EVENT_CURSOR_INVALID", "日志事件游标必须是非负整数");
    }

    private static long parseLong(String value, long defaultValue, String code, String message) {
        if (value == null || value.isBlank()) {
            return defaultValue;
        }
        try {
            long parsed = Long.parseLong(value.trim());
            if (parsed < 0) {
                throw new NumberFormatException("negative");
            }
            return parsed;
        } catch (NumberFormatException ex) {
            throw invalid(code, message);
        }
    }

    private static ApiException invalid(String code, String message) {
        return new ApiException(HttpStatus.BAD_REQUEST, code, message);
    }
}
