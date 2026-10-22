package cn.rvport.backend.report;

import java.util.List;

public record ReportInputProjection(
        String sourceType,
        String riskLevel,
        String moduleKey,
        String moduleName,
        String moduleBasis,
        String moduleConfidence,
        List<String> relatedModuleKeys,
        String fileKey,
        String relativePath,
        String findingType,
        Integer lineStart,
        Integer lineEnd,
        Integer columnStart,
        Integer columnEnd,
        String symbol,
        String sourceContentHash,
        boolean locationAvailable
) {
    public ReportInputProjection {
        relatedModuleKeys = relatedModuleKeys == null ? List.of() : List.copyOf(relatedModuleKeys);
    }

    public static ReportInputProjection none(String sourceType, String riskLevel) {
        return new ReportInputProjection(sourceType, riskLevel, null, null, null, null, List.of(),
                null, null, null, null, null, null, null, null, null, false);
    }

    public ReportInputProjection withSourceContentHash(String hash) {
        return new ReportInputProjection(sourceType, riskLevel, moduleKey, moduleName, moduleBasis, moduleConfidence,
                relatedModuleKeys, fileKey, relativePath, findingType, lineStart, lineEnd, columnStart, columnEnd,
                symbol, hash, locationAvailable);
    }
}
