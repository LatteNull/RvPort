package cn.rvport.backend.task;

import java.util.UUID;

public record TaskLogSseBroadcastMessage(
        long eventId,
        UUID taskId,
        String publisherId
) {
}
