package cn.rvport.backend.buildvalidation.bitcode;

import cn.rvport.backend.artifact.StoredArtifactView;
import java.util.List;

public record BitcodeGenerationResult(BitcodeSummary summary, List<StoredArtifactView> artifacts) {
    public static BitcodeGenerationResult unavailable(BitcodeStatus status, BitcodeReasonCode reasonCode) {
        return new BitcodeGenerationResult(BitcodeSummary.unavailable(status, reasonCode), List.of());
    }
}
