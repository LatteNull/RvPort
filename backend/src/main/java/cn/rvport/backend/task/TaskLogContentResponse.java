package cn.rvport.backend.task;

import java.util.Map;
import java.util.UUID;

public record TaskLogContentResponse(
        Map<String, LogContent> logs
) {
    public record LogContent(
            String type,
            UUID logId,
            long offset,
            int lines,
            int returnedLines,
            long totalLines,
            boolean hasMore,
            String content
    ) {
    }
}
