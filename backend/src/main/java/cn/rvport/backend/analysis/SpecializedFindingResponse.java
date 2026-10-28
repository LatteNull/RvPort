package cn.rvport.backend.analysis;

import cn.rvport.backend.migration.NodeReportInclusionState;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record SpecializedFindingResponse(
        UUID id, UUID runId, SpecializedAnalyzerType analyzerType, String externalFindingId,
        String findingKind, String findingCode, String category, String severity, String confidence,
        String resultStatus, String title, String titleEn, String message, String messageEn,
        String suggestion, String suggestionEn, String testSuggestion, String testSuggestionEn,
        String filePath, Integer startLine, Integer startColumn, Integer endLine, Integer endColumn,
        boolean requiresHumanConfirmation, String semanticDigest, Map<String, Object> detail,
        NodeReportInclusionState reportInclusion, OffsetDateTime createdAt,
        SpecializedFindingCodeContextResponse codeContext, String codeContextUnavailableReason
) {
    public static SpecializedFindingResponse from(SpecializedAnalysisFindingView value, NodeReportInclusionState state) {
        return from(value, state, null, null);
    }

    public static SpecializedFindingResponse from(SpecializedAnalysisFindingView value, NodeReportInclusionState state,
            SpecializedFindingCodeContextResponse context, String unavailableReason) {
        String kind = value.analyzerType() == SpecializedAnalyzerType.MEMORY_ORDER
                ? MemoryOrderResultPolicy.kind(value.findingKind(), value.detail()) : value.findingKind();
        boolean pending = value.analyzerType() == SpecializedAnalyzerType.MEMORY_ORDER && MemoryOrderResultPolicy.pending(kind);
        return new SpecializedFindingResponse(value.id(), value.runId(), value.analyzerType(), value.externalFindingId(),
                kind, value.findingCode(), value.category(), pending ? "INFO" : value.severity(), pending ? null : value.confidence(),
                value.resultStatus(), value.title(), value.titleEn(), value.message(), value.messageEn(),
                value.suggestion(), value.suggestionEn(), value.testSuggestion(), value.testSuggestionEn(),
                value.filePath(), value.startLine(), value.startColumn(), value.endLine(), value.endColumn(),
                pending || value.requiresHumanConfirmation(), value.semanticDigest(), value.detail(), state, value.createdAt(),
                context, unavailableReason);
    }
}
