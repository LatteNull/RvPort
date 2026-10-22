package cn.rvport.backend.source;

import cn.rvport.backend.jooq.tables.records.SourceImportsRecord;
import cn.rvport.backend.task.TaskStatus;
import java.time.OffsetDateTime;
import java.util.UUID;

public record SourceImportView(
        UUID id,
        UUID projectId,
        UUID sourceRevisionId,
        UUID taskId,
        SourceRevisionType inputType,
        TaskStatus status,
        String errorMessage,
        OffsetDateTime createdAt
) {
    public static SourceImportView from(SourceImportsRecord record) {
        return new SourceImportView(
                record.getId(),
                record.getProjectId(),
                record.getSourceRevisionId(),
                record.getTaskId(),
                SourceRevisionType.valueOf(record.getInputType()),
                TaskStatus.valueOf(record.getStatus()),
                record.getErrorMessage(),
                record.getCreatedAt()
        );
    }
}
