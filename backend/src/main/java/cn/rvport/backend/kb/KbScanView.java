package cn.rvport.backend.kb;

import cn.rvport.backend.jooq.tables.records.KbScanRunsRecord;
import cn.rvport.backend.task.TaskStatus;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record KbScanView(
        UUID id,
        UUID projectId,
        UUID taskId,
        UUID sourceRevisionId,
        String kbVersion,
        Map<String, Object> scope,
        TaskStatus status,
        Map<String, Object> summary,
        OffsetDateTime startedAt,
        OffsetDateTime finishedAt
) {
    static KbScanView from(KbScanRunsRecord record, Map<String, Object> scope, Map<String, Object> summary) {
        return new KbScanView(
                record.getId(),
                record.getProjectId(),
                record.getTaskId(),
                record.getSourceRevisionId(),
                record.getKbVersion(),
                scope,
                TaskStatus.valueOf(record.getStatus()),
                summary,
                record.getStartedAt(),
                record.getFinishedAt()
        );
    }
}
