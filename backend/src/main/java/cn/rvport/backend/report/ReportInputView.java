package cn.rvport.backend.report;

import cn.rvport.backend.jooq.tables.records.ReportInputsRecord;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record ReportInputView(
        UUID id,
        UUID reportId,
        ReportInputType inputType,
        UUID inputId,
        Map<String, Object> inputSnapshot,
        OffsetDateTime createdAt
) {
    public static ReportInputView from(ReportInputsRecord record, Map<String, Object> snapshot) {
        return new ReportInputView(
                record.getId(),
                record.getReportId(),
                ReportInputType.valueOf(record.getInputType()),
                record.getInputId(),
                snapshot,
                record.getCreatedAt()
        );
    }
}
