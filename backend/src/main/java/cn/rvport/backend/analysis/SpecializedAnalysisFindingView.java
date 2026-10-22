package cn.rvport.backend.analysis;

import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record SpecializedAnalysisFindingView(
        UUID id,
        UUID runId,
        UUID projectId,
        UUID sourceRevisionId,
        SpecializedAnalyzerType analyzerType,
        String externalFindingId,
        String findingKind,
        String findingCode,
        String category,
        String severity,
        String confidence,
        String resultStatus,
        String title,
        String titleEn,
        String message,
        String messageEn,
        String suggestion,
        String suggestionEn,
        String testSuggestion,
        String testSuggestionEn,
        String filePath,
        Integer startLine,
        Integer startColumn,
        Integer endLine,
        Integer endColumn,
        boolean requiresHumanConfirmation,
        String semanticDigest,
        Map<String, Object> detail,
        OffsetDateTime createdAt
) {
}
