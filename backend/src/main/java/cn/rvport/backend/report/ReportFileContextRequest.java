package cn.rvport.backend.report;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

public record ReportFileContextRequest(
        @Min(1) Integer fromLine,
        @Min(1) @Max(2000) Integer lines
) {
    public int normalizedLines() {
        return lines == null ? 500 : lines;
    }
}
