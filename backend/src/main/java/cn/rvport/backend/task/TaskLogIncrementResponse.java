package cn.rvport.backend.task;

import java.util.Map;
import java.util.UUID;

public record TaskLogIncrementResponse(
        UUID taskId,
        Long fromEventId,
        long latestEventId,
        boolean hasMore,
        Map<String, LogIncrement> logs
) {
    public record LogIncrement(String content, int returnedEvents) {
    }
}
