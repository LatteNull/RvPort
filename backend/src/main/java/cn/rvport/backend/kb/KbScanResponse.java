package cn.rvport.backend.kb;

import java.time.OffsetDateTime;
import java.util.ArrayList;
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
        OffsetDateTime finishedAt
) {
    static KbScanResponse from(KbScanView view) {
        return from(view, false);
    }

    static KbScanResponse from(KbScanView view, boolean currentSourceRevision) {
        return new KbScanResponse(
                view.id(),
                view.projectId(),
                view.taskId(),
                view.sourceRevisionId(),
                view.kbVersion(),
                view.scope(),
                view.status().name(),
                currentSourceRevision,
                staleReasons(currentSourceRevision),
                view.summary(),
                view.startedAt(),
                view.finishedAt()
        );
    }

    private static List<String> staleReasons(boolean currentSourceRevision) {
        List<String> reasons = new ArrayList<>();
        if (!currentSourceRevision) {
            reasons.add("SOURCE_REVISION_CHANGED");
        }
        return List.copyOf(reasons);
    }
}
