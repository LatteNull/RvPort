package cn.rvport.backend.analysis;

import java.util.Map;

public record SpecializedFindingImport(
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
        Map<String, Object> detail
) {
}
