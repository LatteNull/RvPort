package cn.rvport.backend.source;

import cn.rvport.backend.task.TaskStatus;
import java.time.OffsetDateTime;
import java.util.UUID;

public record SourceImportResponse(
        UUID id,
        UUID projectId,
        UUID sourceRevisionId,
        UUID taskId,
        SourceRevisionType inputType,
        TaskStatus status,
        String errorMessage,
        OffsetDateTime createdAt
) {
    public static SourceImportResponse from(SourceImportView view) {
        return new SourceImportResponse(
                view.id(),
                view.projectId(),
                view.sourceRevisionId(),
                view.taskId(),
                view.inputType(),
                view.status(),
                view.errorMessage(),
                view.createdAt()
        );
    }
}
