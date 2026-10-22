package cn.rvport.backend.kb;

import cn.rvport.backend.jooq.tables.records.FindingsRecord;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record FindingView(
        UUID id,
        UUID projectId,
        UUID scanRunId,
        UUID sourceRevisionId,
        String ruleId,
        String category,
        String severity,
        String title,
        String description,
        String filePath,
        Integer lineStart,
        Integer lineEnd,
        String symbol,
        Map<String, Object> evidence,
        String suggestion,
        String fingerprint,
        String status,
        OffsetDateTime createdAt
) {
    static FindingView from(FindingsRecord record, Map<String, Object> evidence) {
        return new FindingView(
                record.getId(),
                record.getProjectId(),
                record.getScanRunId(),
                record.getSourceRevisionId(),
                record.getRuleId(),
                record.getCategory(),
                record.getSeverity(),
                record.getTitle(),
                record.getDescription(),
                record.getFilePath(),
                record.getLineStart(),
                record.getLineEnd(),
                record.getSymbol(),
                evidence,
                record.getSuggestion(),
                record.getFingerprint(),
                record.getStatus(),
                record.getCreatedAt()
        );
    }
}
