package cn.rvport.backend.worker;

import java.time.OffsetDateTime;

public record WorkerInstanceResponse(
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
    static WorkerInstanceResponse from(WorkerInstanceView view) {
        return new WorkerInstanceResponse(
                view.instanceId(),
                view.hostname(),
                view.processId(),
                view.appVersion(),
                view.status(),
                view.concurrencyLimit(),
                view.activeConcurrency(),
                view.activeTaskCount(),
                view.startedAt(),
                view.lastHeartbeatAt(),
                view.createdAt(),
                view.updatedAt()
        );
    }
}
