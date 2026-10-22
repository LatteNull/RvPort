package cn.rvport.backend.optimization;

import cn.rvport.backend.jooq.tables.records.OptimizationCyclesRecord;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record OptimizationCycleView(
        UUID id,
        UUID projectId,
        UUID sourceRevisionId,
        int cycleNumber,
        OptimizationCycleStatus status,
        Map<String, Object> summary,
        OffsetDateTime startedAt,
        OffsetDateTime completedAt,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
    public static OptimizationCycleView from(OptimizationCyclesRecord record, Map<String, Object> summary) {
        return new OptimizationCycleView(
                record.getId(),
                record.getProjectId(),
                record.getSourceRevisionId(),
                record.getCycleNumber(),
                OptimizationCycleStatus.valueOf(record.getStatus()),
                summary == null ? Map.of() : summary,
                record.getStartedAt(),
                record.getCompletedAt(),
                record.getCreatedAt(),
                record.getUpdatedAt()
        );
    }
}
