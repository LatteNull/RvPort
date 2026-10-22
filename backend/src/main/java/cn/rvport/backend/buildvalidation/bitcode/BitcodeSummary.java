package cn.rvport.backend.buildvalidation.bitcode;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

public record BitcodeSummary(
        boolean available,
        BitcodeStatus status,
        BitcodeReasonCode reasonCode,
        String schemaVersion,
        boolean legacy,
        String artifactSetId,
        String sourceIdentityDigest,
        String compileContextDigest,
        String bundleSha256,
        String toolchainId,
        String toolchainVersion,
        int plannedCount,
        int succeededCount,
        int failedCount,
        int skippedCount,
        int warningCount,
        long totalBytes,
        UUID manifestArtifactId,
        UUID bundleArtifactId
) {
    public static BitcodeSummary unavailable(BitcodeStatus status, BitcodeReasonCode reasonCode) {
        return new BitcodeSummary(false, status, reasonCode, BitcodeManifest.SCHEMA_VERSION,
                reasonCode == BitcodeReasonCode.LEGACY_RECORD, null, null, null, null, null, null,
                0, 0, 0, 0, 0, 0, null, null);
    }

    public Map<String, Object> toMap() {
        Map<String, Object> value = new LinkedHashMap<>();
        value.put("available", available);
        value.put("status", status.name());
        value.put("reasonCode", reasonCode.name());
        value.put("schemaVersion", schemaVersion);
        value.put("legacy", legacy);
        value.put("artifactSetId", artifactSetId);
        value.put("sourceIdentityDigest", sourceIdentityDigest);
        value.put("compileContextDigest", compileContextDigest);
        value.put("bundleSha256", bundleSha256);
        value.put("toolchainId", toolchainId);
        value.put("toolchainVersion", toolchainVersion);
        value.put("plannedCount", plannedCount);
        value.put("succeededCount", succeededCount);
        value.put("failedCount", failedCount);
        value.put("skippedCount", skippedCount);
        value.put("warningCount", warningCount);
        value.put("totalBytes", totalBytes);
        value.put("manifestArtifactId", manifestArtifactId);
        value.put("bundleArtifactId", bundleArtifactId);
        return value;
    }
}
