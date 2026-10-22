package cn.rvport.backend.analysis;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import cn.rvport.backend.artifact.StoredArtifactOwnerType;
import cn.rvport.backend.artifact.StoredArtifactService;
import cn.rvport.backend.artifact.StoredArtifactView;
import cn.rvport.backend.buildvalidation.BuildValidationArtifacts;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class SpecializedBitcodeCapabilityResolverTests {

    private final StoredArtifactService artifacts = mock(StoredArtifactService.class);
    private final SpecializedBitcodeCapabilityResolver resolver = new SpecializedBitcodeCapabilityResolver(artifacts);
    private final UUID buildId = UUID.randomUUID();

    @Test
    void missingArtifactsDegradeToAstOnly() {
        StoredArtifactView compileDatabase = artifact(BuildValidationArtifacts.COMPILE_COMMANDS_JSON,
                Map.of("commandCount", 7));
        when(artifacts.findByOwner(StoredArtifactOwnerType.BUILD_VALIDATION, buildId,
                BuildValidationArtifacts.COMPILE_COMMANDS_JSON)).thenReturn(Optional.of(compileDatabase));
        SpecializedBitcodeCapability value = resolver.resolve(buildId);
        assertThat(value.mode()).isEqualTo(SpecializedAnalysisMode.AST_ONLY);
        assertThat(value.plannedCount()).isEqualTo(7);
        assertThat(value.astOnlyCount()).isEqualTo(7);
        assertThat(value.degradationReason()).isEqualTo("BITCODE_ARTIFACTS_MISSING");
    }

    @Test
    void completeAndPartialCoverageAreDistinguished() {
        StoredArtifactView compileDatabase = artifact(BuildValidationArtifacts.COMPILE_COMMANDS_JSON,
                Map.of("commandCount", 3));
        when(artifacts.findByOwner(StoredArtifactOwnerType.BUILD_VALIDATION, buildId,
                BuildValidationArtifacts.COMPILE_COMMANDS_JSON)).thenReturn(Optional.of(compileDatabase));
        StoredArtifactView bundle = artifact(BuildValidationArtifacts.LLVM_BITCODE_BUNDLE_TGZ, Map.of());
        when(artifacts.findByOwner(StoredArtifactOwnerType.BUILD_VALIDATION, buildId,
                BuildValidationArtifacts.LLVM_BITCODE_BUNDLE_TGZ)).thenReturn(Optional.of(bundle));
        when(artifacts.objectExists(bundle)).thenReturn(true);

        StoredArtifactView complete = artifact(BuildValidationArtifacts.LLVM_BITCODE_MANIFEST_JSON,
                Map.of("schemaVersion", "2.1", "artifactSetId", "a".repeat(64), "plannedCount", 2,
                        "succeededCount", 2, "failedCount", 0, "status", "READY"));
        when(artifacts.findByOwner(StoredArtifactOwnerType.BUILD_VALIDATION, buildId,
                BuildValidationArtifacts.LLVM_BITCODE_MANIFEST_JSON)).thenReturn(Optional.of(complete));
        when(artifacts.objectExists(complete)).thenReturn(true);
        assertThat(resolver.resolve(buildId).mode()).isEqualTo(SpecializedAnalysisMode.AST_BC_COMPLETE);

        when(artifacts.findByOwner(StoredArtifactOwnerType.BUILD_VALIDATION, buildId,
                BuildValidationArtifacts.COMPILE_COMMANDS_JSON)).thenReturn(Optional.of(
                        artifact(BuildValidationArtifacts.COMPILE_COMMANDS_JSON, Map.of("commandCount", 2))));
        assertThat(resolver.resolve(buildId).mode()).isEqualTo(SpecializedAnalysisMode.AST_BC_COMPLETE);

        StoredArtifactView partial = artifact(BuildValidationArtifacts.LLVM_BITCODE_MANIFEST_JSON,
                Map.of("schemaVersion", "2.1", "artifactSetId", "b".repeat(64), "plannedCount", 3,
                        "succeededCount", 1, "failedCount", 2, "status", "PARTIAL"));
        when(artifacts.findByOwner(StoredArtifactOwnerType.BUILD_VALIDATION, buildId,
                BuildValidationArtifacts.LLVM_BITCODE_MANIFEST_JSON)).thenReturn(Optional.of(partial));
        when(artifacts.objectExists(partial)).thenReturn(true);
        SpecializedBitcodeCapability value = resolver.resolve(buildId);
        assertThat(value.mode()).isEqualTo(SpecializedAnalysisMode.AST_BC_MIXED);
        assertThat(value.astOnlyCount()).isEqualTo(2);
    }

    @Test
    void invalidIdentityAndZeroUsableRecordsDegradeSafely() {
        StoredArtifactView bundle = artifact(BuildValidationArtifacts.LLVM_BITCODE_BUNDLE_TGZ, Map.of());
        StoredArtifactView manifest = artifact(BuildValidationArtifacts.LLVM_BITCODE_MANIFEST_JSON,
                Map.of("schemaVersion", "1.0", "plannedCount", 1, "succeededCount", 0));
        when(artifacts.findByOwner(StoredArtifactOwnerType.BUILD_VALIDATION, buildId,
                BuildValidationArtifacts.LLVM_BITCODE_MANIFEST_JSON)).thenReturn(Optional.of(manifest));
        when(artifacts.findByOwner(StoredArtifactOwnerType.BUILD_VALIDATION, buildId,
                BuildValidationArtifacts.LLVM_BITCODE_BUNDLE_TGZ)).thenReturn(Optional.of(bundle));
        when(artifacts.objectExists(manifest)).thenReturn(true);
        when(artifacts.objectExists(bundle)).thenReturn(true);
        assertThat(resolver.resolve(buildId).degradationReason()).isEqualTo("BITCODE_MANIFEST_IDENTITY_INVALID");
    }

    @Test
    void incompleteOrMissingObjectsDegradeWithoutTrustingManifestMetadata() {
        StoredArtifactView manifest = artifact(BuildValidationArtifacts.LLVM_BITCODE_MANIFEST_JSON,
                Map.of("plannedCount", 4, "failedCount", 2));
        when(artifacts.findByOwner(StoredArtifactOwnerType.BUILD_VALIDATION, buildId,
                BuildValidationArtifacts.LLVM_BITCODE_MANIFEST_JSON)).thenReturn(Optional.of(manifest));
        when(artifacts.objectExists(manifest)).thenReturn(false);

        SpecializedBitcodeCapability value = resolver.resolve(buildId);

        assertThat(value.mode()).isEqualTo(SpecializedAnalysisMode.AST_ONLY);
        assertThat(value.status()).isEqualTo("INVALID");
        assertThat(value.plannedCount()).isEqualTo(4);
        assertThat(value.failedCount()).isEqualTo(2);
        assertThat(value.degradationReason()).isEqualTo("BITCODE_ARTIFACT_PAIR_INCOMPLETE");
    }

    @Test
    void validManifestWithNoUsableRecordsReportsFailedAstOnlyCapability() {
        StoredArtifactView manifest = artifact(BuildValidationArtifacts.LLVM_BITCODE_MANIFEST_JSON,
                Map.of("schemaVersion", "2.0", "artifactSetId", "set", "plannedCount", 3,
                        "succeededCount", 0, "failedCount", 3, "status", "FAILED"));
        StoredArtifactView bundle = artifact(BuildValidationArtifacts.LLVM_BITCODE_BUNDLE_TGZ, Map.of());
        when(artifacts.findByOwner(StoredArtifactOwnerType.BUILD_VALIDATION, buildId,
                BuildValidationArtifacts.LLVM_BITCODE_MANIFEST_JSON)).thenReturn(Optional.of(manifest));
        when(artifacts.findByOwner(StoredArtifactOwnerType.BUILD_VALIDATION, buildId,
                BuildValidationArtifacts.LLVM_BITCODE_BUNDLE_TGZ)).thenReturn(Optional.of(bundle));
        when(artifacts.objectExists(manifest)).thenReturn(true);
        when(artifacts.objectExists(bundle)).thenReturn(true);

        SpecializedBitcodeCapability value = resolver.resolve(buildId);

        assertThat(value.mode()).isEqualTo(SpecializedAnalysisMode.AST_ONLY);
        assertThat(value.status()).isEqualTo("FAILED");
        assertThat(value.degradationReason()).isEqualTo("BITCODE_HAS_NO_USABLE_RECORDS");
        assertThat(value.manifest()).isNull();
        assertThat(value.bundle()).isNull();
    }

    @Test
    void malformedAndNegativeCountersAreTreatedAsZero() {
        StoredArtifactView compileDatabase = artifact(BuildValidationArtifacts.COMPILE_COMMANDS_JSON,
                Map.of("commandCount", "unknown"));
        StoredArtifactView manifest = artifact(BuildValidationArtifacts.LLVM_BITCODE_MANIFEST_JSON,
                Map.of("schemaVersion", "2.1", "artifactSetId", "set", "plannedCount", -2,
                        "succeededCount", 1, "failedCount", -1));
        StoredArtifactView bundle = artifact(BuildValidationArtifacts.LLVM_BITCODE_BUNDLE_TGZ, Map.of());
        when(artifacts.findByOwner(StoredArtifactOwnerType.BUILD_VALIDATION, buildId,
                BuildValidationArtifacts.COMPILE_COMMANDS_JSON)).thenReturn(Optional.of(compileDatabase));
        when(artifacts.findByOwner(StoredArtifactOwnerType.BUILD_VALIDATION, buildId,
                BuildValidationArtifacts.LLVM_BITCODE_MANIFEST_JSON)).thenReturn(Optional.of(manifest));
        when(artifacts.findByOwner(StoredArtifactOwnerType.BUILD_VALIDATION, buildId,
                BuildValidationArtifacts.LLVM_BITCODE_BUNDLE_TGZ)).thenReturn(Optional.of(bundle));
        when(artifacts.objectExists(manifest)).thenReturn(true);
        when(artifacts.objectExists(bundle)).thenReturn(true);

        SpecializedBitcodeCapability value = resolver.resolve(buildId);

        assertThat(value.mode()).isEqualTo(SpecializedAnalysisMode.AST_BC_MIXED);
        assertThat(value.plannedCount()).isZero();
        assertThat(value.failedCount()).isZero();
    }

    @Test
    void manifestMissingWhileBundleExistsIsAnIncompletePair() {
        StoredArtifactView bundle = artifact(BuildValidationArtifacts.LLVM_BITCODE_BUNDLE_TGZ, Map.of());
        when(artifacts.findByOwner(StoredArtifactOwnerType.BUILD_VALIDATION, buildId,
                BuildValidationArtifacts.LLVM_BITCODE_BUNDLE_TGZ)).thenReturn(Optional.of(bundle));

        assertThat(resolver.resolve(buildId).degradationReason())
                .isEqualTo("BITCODE_ARTIFACT_PAIR_INCOMPLETE");
    }

    @Test
    void missingBundleObjectAndBlankArtifactIdentityAreRejected() {
        StoredArtifactView manifest = artifact(BuildValidationArtifacts.LLVM_BITCODE_MANIFEST_JSON,
                Map.of("schemaVersion", "2.1", "artifactSetId", " ", "succeededCount", 1));
        StoredArtifactView bundle = artifact(BuildValidationArtifacts.LLVM_BITCODE_BUNDLE_TGZ, Map.of());
        when(artifacts.findByOwner(StoredArtifactOwnerType.BUILD_VALIDATION, buildId,
                BuildValidationArtifacts.LLVM_BITCODE_MANIFEST_JSON)).thenReturn(Optional.of(manifest));
        when(artifacts.findByOwner(StoredArtifactOwnerType.BUILD_VALIDATION, buildId,
                BuildValidationArtifacts.LLVM_BITCODE_BUNDLE_TGZ)).thenReturn(Optional.of(bundle));
        when(artifacts.objectExists(manifest)).thenReturn(true);
        when(artifacts.objectExists(bundle)).thenReturn(false, true);

        assertThat(resolver.resolve(buildId).degradationReason())
                .isEqualTo("BITCODE_ARTIFACT_PAIR_INCOMPLETE");
        assertThat(resolver.resolve(buildId).degradationReason())
                .isEqualTo("BITCODE_MANIFEST_IDENTITY_INVALID");
    }

    private StoredArtifactView artifact(String type, Map<String, Object> summary) {
        return new StoredArtifactView(UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(),
                StoredArtifactOwnerType.BUILD_VALIDATION, buildId, type, "bucket", type,
                "application/octet-stream", 1, "a".repeat(64), summary, OffsetDateTime.now());
    }
}
