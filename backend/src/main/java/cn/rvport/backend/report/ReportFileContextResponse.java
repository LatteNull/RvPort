package cn.rvport.backend.report;

import java.util.List;
import java.util.UUID;

public record ReportFileContextResponse(
        UUID reportId,
        UUID sourceRevisionId,
        String fileKey,
        String relativePath,
        String contentHash,
        Integer totalLines,
        boolean contextAvailable,
        String unavailableReason,
        List<ReportCodeFindingResponse> findings,
        List<Block> blocks
) {
    public record Block(
            String kind,
            int startLine,
            int endLine,
            int lineCount,
            String reason,
            boolean loadable,
            List<Line> lines
    ) {
    }

    public record Line(int lineNumber, String text, List<Highlight> highlights) {
    }

    public record Highlight(UUID findingId, Integer columnStart, Integer columnEnd) {
    }
}
