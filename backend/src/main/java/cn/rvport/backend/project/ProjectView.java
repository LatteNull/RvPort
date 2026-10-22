package cn.rvport.backend.project;

import cn.rvport.backend.jooq.tables.records.ProjectsRecord;
import java.time.OffsetDateTime;
import java.util.UUID;

public record ProjectView(
        UUID id,
        String name,
        String description,
        String sourceArch,
        String targetArch,
        ProjectStage stage,
        ProjectStatus status,
        ProjectSourceInputType sourceInputType,
        UUID createdBy,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
    public static ProjectView from(ProjectsRecord record) {
        return new ProjectView(
                record.getId(),
                record.getName(),
                record.getDescription(),
                record.getSourceArch(),
                record.getTargetArch(),
                ProjectStage.valueOf(record.getStage()),
                ProjectStatus.valueOf(record.getStatus()),
                parseSourceInputType(record.getSourceInputType()),
                record.getCreatedBy(),
                record.getCreatedAt(),
                record.getUpdatedAt()
        );
    }

    private static ProjectSourceInputType parseSourceInputType(String value) {
        return value == null || value.isBlank() ? null : ProjectSourceInputType.valueOf(value);
    }
}
