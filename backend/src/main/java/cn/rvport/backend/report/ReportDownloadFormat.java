package cn.rvport.backend.report;

public enum ReportDownloadFormat {
    HTML("MIGRATION_REPORT_HTML", "text/html", "html"),
    JSON("MIGRATION_REPORT_JSON", "application/json", "json");

    private final String artifactType;
    private final String contentType;
    private final String extension;

    ReportDownloadFormat(String artifactType, String contentType, String extension) {
        this.artifactType = artifactType;
        this.contentType = contentType;
        this.extension = extension;
    }

    public String artifactType() {
        return artifactType;
    }

    public String contentType() {
        return contentType;
    }

    public String extension() {
        return extension;
    }

    public static ReportDownloadFormat parse(String value) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("Report format is required");
        }
        return ReportDownloadFormat.valueOf(value.trim().toUpperCase());
    }
}
