package cn.rvport.backend.analysis;

import cn.rvport.backend.artifact.StoredArtifactView;
import java.util.Map;

public record SpecializedBitcodeCapability(
        SpecializedAnalysisMode mode,
        String status,
        int plannedCount,
        int usableCount,
        int failedCount,
        String degradationReason,
        StoredArtifactView manifest,
        StoredArtifactView bundle,
        String artifactSetId,
        Map<String, Object> audit
) {
    public SpecializedBitcodeCapability(
            SpecializedAnalysisMode mode, String status, int plannedCount, int usableCount,
            int failedCount, String degradationReason, StoredArtifactView manifest,
            StoredArtifactView bundle, String artifactSetId
    ) {
        this(mode, status, plannedCount, usableCount, failedCount, degradationReason,
                manifest, bundle, artifactSetId, Map.of());
    }

    public SpecializedBitcodeCapability {
        audit = audit == null ? Map.of() : Map.copyOf(audit);
    }
    public int astOnlyCount() {
        return Math.max(0, plannedCount - usableCount);
    }

    public boolean hasUsableBitcode() {
        return mode != SpecializedAnalysisMode.AST_ONLY && artifactSetId != null && !artifactSetId.isBlank();
    }
}
