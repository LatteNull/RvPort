package cn.rvport.backend.analysis;

import cn.rvport.backend.artifact.StoredArtifactOwnerType;
import cn.rvport.backend.artifact.StoredArtifactService;
import cn.rvport.backend.artifact.StoredArtifactView;
import cn.rvport.backend.buildvalidation.BuildValidationArtifacts;
import java.util.Objects;
import java.util.UUID;
import org.springframework.stereotype.Service;

@Service
public class SpecializedBitcodeCapabilityResolver {

    private final StoredArtifactService artifactService;

    public SpecializedBitcodeCapabilityResolver(StoredArtifactService artifactService) {
        this.artifactService = artifactService;
    }

    public SpecializedBitcodeCapability resolve(UUID buildRunId) {
        StoredArtifactView compileDatabase = find(buildRunId, BuildValidationArtifacts.COMPILE_COMMANDS_JSON);
        int compileDatabaseCount = number(compileDatabase, "commandCount");
        StoredArtifactView manifest = find(buildRunId, BuildValidationArtifacts.LLVM_BITCODE_MANIFEST_JSON);
        StoredArtifactView bundle = find(buildRunId, BuildValidationArtifacts.LLVM_BITCODE_BUNDLE_TGZ);
        if (manifest == null && bundle == null) {
            return astOnly("MISSING", compileDatabaseCount, 0, "BITCODE_ARTIFACTS_MISSING");
        }
        if (manifest == null || bundle == null || !artifactService.objectExists(manifest)
                || !artifactService.objectExists(bundle)) {
            return astOnly("INVALID", planned(manifest, compileDatabaseCount),
                    number(manifest, "failedCount"),
                    "BITCODE_ARTIFACT_PAIR_INCOMPLETE");
        }
        String schemaVersion = Objects.toString(manifest.summary().get("schemaVersion"), "");
        int planned = planned(manifest, compileDatabaseCount);
        int usable = number(manifest, "succeededCount");
        int failed = number(manifest, "failedCount");
        String artifactSetId = Objects.toString(manifest.summary().get("artifactSetId"), "");
        if (!("2.0".equals(schemaVersion) || "2.1".equals(schemaVersion)) || artifactSetId.isBlank()) {
            return astOnly("INVALID", planned, failed, "BITCODE_MANIFEST_IDENTITY_INVALID");
        }
        if (usable <= 0) {
            return new SpecializedBitcodeCapability(SpecializedAnalysisMode.AST_ONLY,
                    Objects.toString(manifest.summary().get("status"), "FAILED"), planned, 0, failed,
                    "BITCODE_HAS_NO_USABLE_RECORDS", null, null, null);
        }
        SpecializedAnalysisMode mode = planned > 0 && usable >= planned
                ? SpecializedAnalysisMode.AST_BC_COMPLETE : SpecializedAnalysisMode.AST_BC_MIXED;
        return new SpecializedBitcodeCapability(mode,
                Objects.toString(manifest.summary().get("status"), mode == SpecializedAnalysisMode.AST_BC_COMPLETE
                        ? "READY" : "PARTIAL"), planned, usable, failed,
                mode == SpecializedAnalysisMode.AST_BC_MIXED ? "BITCODE_PARTIAL_COVERAGE" : null,
                manifest, bundle, artifactSetId);
    }

    private StoredArtifactView find(UUID buildRunId, String type) {
        return artifactService.findByOwner(StoredArtifactOwnerType.BUILD_VALIDATION, buildRunId, type).orElse(null);
    }

    private SpecializedBitcodeCapability astOnly(String status, int planned, int failed, String reason) {
        return new SpecializedBitcodeCapability(SpecializedAnalysisMode.AST_ONLY, status, planned, 0, failed,
                reason, null, null, null);
    }

    private int number(StoredArtifactView artifact, String key) {
        if (artifact == null) return 0;
        Object value = artifact.summary().get(key);
        return value instanceof Number number ? Math.max(0, number.intValue()) : 0;
    }

    private int planned(StoredArtifactView manifest, int fallback) {
        int manifestPlanned = number(manifest, "plannedCount");
        return manifestPlanned > 0 ? manifestPlanned : fallback;
    }
}
