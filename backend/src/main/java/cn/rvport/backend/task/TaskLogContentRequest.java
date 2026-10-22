package cn.rvport.backend.task;

import cn.rvport.backend.common.error.ApiException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import org.springframework.http.HttpStatus;

public record TaskLogContentRequest(
        List<Entry> entries
) {
    static final int DEFAULT_LINES = 100;
    static final int MAX_LINES = 5000;

    public static TaskLogContentRequest from(
            String types,
            Integer lines,
            Long mergedOffset,
            Long stdoutOffset,
            Long stderrOffset,
            Integer mergedLines,
            Integer stdoutLines,
            Integer stderrLines
    ) {
        int defaultLines = normalizeLines(lines == null ? DEFAULT_LINES : lines);
        Map<String, Entry> entries = new LinkedHashMap<>();
        for (String type : parseTypes(types)) {
            entries.put(type, new Entry(
                    type,
                    toLogType(type),
                    normalizeOffset(switch (type) {
                        case "merged" -> mergedOffset;
                        case "stdout" -> stdoutOffset;
                        case "stderr" -> stderrOffset;
                        default -> null;
                    }),
                    normalizeLines(switch (type) {
                        case "merged" -> mergedLines == null ? defaultLines : mergedLines;
                        case "stdout" -> stdoutLines == null ? defaultLines : stdoutLines;
                        case "stderr" -> stderrLines == null ? defaultLines : stderrLines;
                        default -> defaultLines;
                    })
            ));
        }
        return new TaskLogContentRequest(List.copyOf(entries.values()));
    }

    private static List<String> parseTypes(String rawTypes) {
        if (rawTypes == null || rawTypes.isBlank()) {
            return List.of("merged", "stdout", "stderr");
        }
        List<String> result = new ArrayList<>();
        for (String raw : rawTypes.split(",")) {
            String type = raw.trim().toLowerCase(Locale.ROOT);
            if (type.isBlank()) {
                continue;
            }
            if (!type.equals("merged") && !type.equals("stdout") && !type.equals("stderr")) {
                throw invalid("TASK_LOG_TYPE_INVALID", "日志类型不支持");
            }
            if (!result.contains(type)) {
                result.add(type);
            }
        }
        if (result.isEmpty()) {
            throw invalid("TASK_LOG_TYPE_INVALID", "日志类型不能为空");
        }
        return result;
    }

    private static TaskLogType toLogType(String type) {
        return switch (type) {
            case "merged" -> TaskLogType.COMBINED;
            case "stdout" -> TaskLogType.STDOUT;
            case "stderr" -> TaskLogType.STDERR;
            default -> throw invalid("TASK_LOG_TYPE_INVALID", "日志类型不支持");
        };
    }

    private static long normalizeOffset(Long offset) {
        if (offset == null) {
            return 0L;
        }
        if (offset < 0) {
            throw invalid("TASK_LOG_OFFSET_INVALID", "日志 offset 不能为负数");
        }
        return offset;
    }

    private static int normalizeLines(Integer lines) {
        if (lines == null) {
            return DEFAULT_LINES;
        }
        if (lines < 0) {
            throw invalid("TASK_LOG_LINES_INVALID", "日志行数不能为负数");
        }
        if (lines > MAX_LINES) {
            throw invalid("TASK_LOG_LINES_INVALID", "日志行数超过上限");
        }
        return lines;
    }

    private static ApiException invalid(String code, String message) {
        return new ApiException(HttpStatus.BAD_REQUEST, code, message);
    }

    public record Entry(
            String type,
            TaskLogType logType,
            long offset,
            int lines
    ) {
    }
}
