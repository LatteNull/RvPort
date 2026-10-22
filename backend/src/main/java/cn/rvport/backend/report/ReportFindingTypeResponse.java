package cn.rvport.backend.report;

public record ReportFindingTypeResponse(
        String findingType,
        long findingCount,
        String highestRisk,
        Integer firstLine,
        Integer lastLine,
        long symbolCount
) {
}
