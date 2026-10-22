package cn.rvport.backend.worker;

import java.time.OffsetDateTime;

public record WorkerInstanceView(
        String instanceId,
        String hostname,
        Long processId,
        String appVersion,
        WorkerInstanceStatus status,
        int concurrencyLimit,
        int activeConcurrency,
        int activeTaskCount,
        OffsetDateTime startedAt,
        OffsetDateTime lastHeartbeatAt,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
}
