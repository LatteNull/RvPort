package cn.rvport.backend.kb;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public record KbScanResponse(
        UUID id,
        UUID projectId,
        UUID taskId,
        UUID sourceRevisionId,
        String kbVersion,
        Map<String, Object> scope,
        String status,
        boolean currentSourceRevision,
        List<String> staleReasons,
        Map<String, Object> summary,
        OffsetDateTime startedAt,
        OffsetDateTime finishedAt,
        KbExecutionContext executionContext,
        boolean current,
        String message,
        String message_en
) {
    static KbScanResponse from(KbScanView view, KbScanContextService.Selection selection) {
        String reason = selection.staleReason(view);
        boolean current = reason == null;
        return new KbScanResponse(view.id(), view.projectId(), view.taskId(), view.sourceRevisionId(),
                view.kbVersion(), view.scope(), view.status().name(),
                java.util.Objects.equals(view.sourceRevisionId(), selection.sourceRevisionId()),
                current ? List.of() : List.of(reason), view.summary(), view.startedAt(), view.finishedAt(),
                view.executionContext(), current, current ? "当前扫描结果" : "历史扫描结果，需在当前构建下重新扫描",
                current ? "Current scan result" : "Historical scan result; scan again against the current build");
    }
}
