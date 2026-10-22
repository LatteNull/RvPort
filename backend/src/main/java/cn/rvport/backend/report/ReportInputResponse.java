package cn.rvport.backend.report;

import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record ReportInputResponse(
        UUID id,
        UUID reportId,
        ReportInputType inputType,
        UUID inputId,
        Map<String, Object> inputSnapshot,
        OffsetDateTime createdAt
) {
    static ReportInputResponse from(ReportInputView view) {
        return new ReportInputResponse(
                view.id(),
                view.reportId(),
                view.inputType(),
                view.inputId(),
                view.inputSnapshot(),
                view.createdAt()
        );
    }
}
