package cn.rvport.backend.report;

public record ReportReadinessIssueResponse(
        String code,
        String message,
        Long count
) {
    public static ReportReadinessIssueResponse of(String code, String message) {
        return new ReportReadinessIssueResponse(code, message, null);
    }

    public static ReportReadinessIssueResponse of(String code, String message, long count) {
        return new ReportReadinessIssueResponse(code, message, count);
    }
}
