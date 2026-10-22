package cn.rvport.backend.analysis;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class SpecializedAnalysisValueObjectsTests {

    @Test
    void legacyTaskInputDerivesAstOnlyAndCompleteModes() {
        UUID projectId = UUID.randomUUID();
        UUID runId = UUID.randomUUID();

        SpecializedAnalysisTaskInput astOnly = new SpecializedAnalysisTaskInput(
                projectId, runId, UUID.randomUUID(), UUID.randomUUID(), null, null, null,
                null, 3L, SpecializedAnalyzerType.FLOATING_POINT);
        SpecializedAnalysisTaskInput complete = new SpecializedAnalysisTaskInput(
                projectId, runId, UUID.randomUUID(), UUID.randomUUID(), null, null, null,
                "artifact-set", 3L, SpecializedAnalyzerType.MEMORY_ORDER);

        assertThat(astOnly.analysisMode()).isEqualTo(SpecializedAnalysisMode.AST_ONLY);
        assertThat(astOnly.bcStatus()).isEqualTo("MISSING");
        assertThat(astOnly.bcPlannedCount()).isZero();
        assertThat(astOnly.bcUsableCount()).isZero();
        assertThat(astOnly.bcDegradationReason()).isEqualTo("BITCODE_ARTIFACTS_MISSING");
        assertThat(complete.analysisMode()).isEqualTo(SpecializedAnalysisMode.AST_BC_COMPLETE);
        assertThat(complete.bcStatus()).isEqualTo("READY");
        assertThat(complete.bcPlannedCount()).isOne();
        assertThat(complete.bcUsableCount()).isOne();
        assertThat(complete.bcDegradationReason()).isNull();
    }

    @Test
    void legacyRunViewPreservesWhetherBitcodeIdentityWasPresent() {
        SpecializedAnalysisRunView astOnly = legacyRun(null);
        SpecializedAnalysisRunView mixed = legacyRun("artifact-set");

        assertThat(astOnly.analysisMode()).isEqualTo(SpecializedAnalysisMode.AST_ONLY);
        assertThat(astOnly.bcStatus()).isEqualTo("UNKNOWN");
        assertThat(astOnly.bcDegradationReason()).isEqualTo("LEGACY_EVIDENCE_UNKNOWN");
        assertThat(mixed.analysisMode()).isEqualTo(SpecializedAnalysisMode.AST_BC_MIXED);
        assertThat(mixed.bcStatus()).isEqualTo("LEGACY_UNKNOWN");
        assertThat(mixed.bcDegradationReason()).isNull();
    }

    @Test
    void capabilityReportsAstOnlyCountAndRequiresUsableArtifactIdentity() {
        SpecializedBitcodeCapability astOnly = new SpecializedBitcodeCapability(
                SpecializedAnalysisMode.AST_ONLY, "MISSING", 2, 0, 2, "missing", null, null, null);
        SpecializedBitcodeCapability blankIdentity = new SpecializedBitcodeCapability(
                SpecializedAnalysisMode.AST_BC_MIXED, "PARTIAL", 3, 1, 2, "partial", null, null, " ");
        SpecializedBitcodeCapability missingIdentity = new SpecializedBitcodeCapability(
                SpecializedAnalysisMode.AST_BC_MIXED, "PARTIAL", 3, 1, 2, "partial", null, null, null);
        SpecializedBitcodeCapability usable = new SpecializedBitcodeCapability(
                SpecializedAnalysisMode.AST_BC_COMPLETE, "READY", 1, 2, 0, null, null, null, "set");

        assertThat(astOnly.astOnlyCount()).isEqualTo(2);
        assertThat(astOnly.hasUsableBitcode()).isFalse();
        assertThat(blankIdentity.hasUsableBitcode()).isFalse();
        assertThat(missingIdentity.hasUsableBitcode()).isFalse();
        assertThat(usable.astOnlyCount()).isZero();
        assertThat(usable.hasUsableBitcode()).isTrue();
    }

    private SpecializedAnalysisRunView legacyRun(String artifactSetId) {
        OffsetDateTime now = OffsetDateTime.now();
        return new SpecializedAnalysisRunView(
                UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), SpecializedAnalyzerType.FLOATING_POINT,
                UUID.randomUUID(), UUID.randomUUID(), artifactSetId, 1L,
                "tool", "request", "result", "policy", SpecializedAnalysisStatus.COMPLETE,
                "PASS", 0, Map.of(), null, null, null, null,
                0, 0, 0, UUID.randomUUID(), now, now, now, now);
    }
}
