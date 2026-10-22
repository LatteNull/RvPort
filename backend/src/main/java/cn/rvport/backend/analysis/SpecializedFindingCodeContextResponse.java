package cn.rvport.backend.analysis;

import java.util.List;
import java.util.UUID;

public record SpecializedFindingCodeContextResponse(
        UUID findingId, UUID runId, UUID sourceRevisionId, String filePath,
        int contextBefore, int contextAfter, int startLine, int endLine,
        int highlightStartLine, int highlightEndLine, List<CodeLine> lines
) {
    public record CodeLine(int lineNumber, String text, boolean highlighted) { }
}
