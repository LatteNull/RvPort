package cn.rvport.backend.kb;

import java.util.List;
import java.util.UUID;

public record FindingCodeContextResponse(
        UUID findingId,
        UUID scanRunId,
        String filePath,
        int contextBefore,
        int contextAfter,
        int startLine,
        int endLine,
        int highlightStartLine,
        int highlightEndLine,
        List<CodeLine> lines
) {
    public record CodeLine(
            int lineNumber,
            String text,
            boolean highlighted
    ) {
    }
}
