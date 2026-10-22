package cn.rvport.backend.report;

import cn.rvport.backend.jooq.tables.records.ReportsRecord;
import cn.rvport.backend.task.TaskStatus;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record ReportView(
        UUID id,
        UUID projectId,
        UUID taskId,
        UUID sourceRevisionId,
        ReportType reportType,
        TaskStatus status,
        String title,
        Map<String, Object> summary,
        String riskLevel,
        UUID generatedBy,
        OffsetDateTime generatedAt,
        OffsetDateTime createdAt
) {
    public static ReportView from(ReportsRecord record, Map<String, Object> summary) {
        return new ReportView(
                record.getId(),
                record.getProjectId(),
                record.getTaskId(),
                record.getSourceRevisionId(),
                ReportType.valueOf(record.getReportType()),
                TaskStatus.valueOf(record.getStatus()),
                record.getTitle(),
                summary,
                record.getRiskLevel(),
                record.getGeneratedBy(),
                record.getGeneratedAt(),
                record.getCreatedAt()
        );
    }
}
