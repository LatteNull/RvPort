package cn.rvport.backend.kb;

public enum KbScanArtifactType {
    SCAN_RESULT_JSON,
    SCAN_REPORT_HTML,
    SCAN_LOG;

    public static KbScanArtifactType fromDownloadFormat(String format) {
        if (format == null || format.isBlank()) {
            throw new IllegalArgumentException("KB artifact download format is required");
        }
        return switch (format.trim().toLowerCase()) {
            case "json" -> SCAN_RESULT_JSON;
            case "html" -> SCAN_REPORT_HTML;
            case "log" -> SCAN_LOG;
            default -> throw new IllegalArgumentException("Unsupported KB artifact download format: " + format);
        };
    }
}
