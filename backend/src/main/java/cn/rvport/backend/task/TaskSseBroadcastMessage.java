package cn.rvport.backend.task;

import java.util.UUID;

public record TaskSseBroadcastMessage(
        long eventId,
        UUID projectId,
        String publisherId
) {
}
