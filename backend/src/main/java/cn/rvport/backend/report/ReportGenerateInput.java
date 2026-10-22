package cn.rvport.backend.report;

import java.util.UUID;

public record ReportGenerateInput(
        UUID projectId,
        UUID sourceRevisionId,
        UUID reportId
) {
}
