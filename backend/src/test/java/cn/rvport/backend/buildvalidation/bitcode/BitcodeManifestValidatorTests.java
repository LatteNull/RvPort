package cn.rvport.backend.buildvalidation.bitcode;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.function.Consumer;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.Test;

class BitcodeManifestValidatorTests {

    private final ObjectMapper mapper = new ObjectMapper().findAndRegisterModules();

    @Test
    void acceptsReadyPartialAndFailedManifests() {
        BitcodeManifest ready = BitcodeTestFixtures.manifest(List.of(
                BitcodeTestFixtures.produced("a", "src/a.c", 8, BitcodeTestFixtures.HASH_A)));
        BitcodeManifest partial = BitcodeTestFixtures.manifest(List.of(
                BitcodeTestFixtures.produced("a", "src/a.c", 8, BitcodeTestFixtures.HASH_A),
                BitcodeTestFixtures.failed("b", "src/b.c"),
                BitcodeTestFixtures.missing("c", "src/c.c")));
        BitcodeManifest failed = BitcodeTestFixtures.manifest(List.of(
                BitcodeTestFixtures.failed("b", "src/b.c")));

        BitcodeManifestValidator.validate(ready, 10, 100);
        BitcodeManifestValidator.validate(partial, 10, 100);
        BitcodeManifestValidator.validate(failed, 10, 100);
        assertThat(partial.counts().plannedRecords()).isEqualTo(3);
        assertThat(partial.counts().produced()).isOne();
    }

    @Test
    void rawCompileDatabaseHashIsAuditEvidenceNotSemanticIdentity() {
        BitcodeManifest valid = valid();
        BitcodeManifest rebuilt = new BitcodeManifest(
                valid.kind(), valid.schemaVersion(), valid.artifactSetId(), valid.sourceIdentityDigest(),
                new BitcodeManifest.CompileContext("c".repeat(64), valid.compileContext().normalizedDigest()),
                valid.producer(), valid.status(), valid.counts(), valid.records(), valid.scopes(),
                valid.generatedAt().plusSeconds(60), valid.semanticDigest());

        BitcodeManifestValidator.validate(rebuilt, 10, 100);
        assertThat(rebuilt.artifactSetId()).isEqualTo(valid.artifactSetId());
    }

    @Test
    void acceptsLegacyAndSupportedLanguageStandardContexts() {
        BitcodeManifest current = valid();

        for (String[] context : List.of(
                new String[] {"c", "c89", "iso", "explicit", "-std=c89"},
                new String[] {"c", "c99", "iso", "explicit", "-std=c99"},
                new String[] {"c", "c23", "iso", "explicit", "-std=c23"},
                new String[] {"c++", "c++03", "iso", "explicit", "-std=c++03"},
                new String[] {"c++", "c++23", "iso", "explicit", "-std=c++23"},
                new String[] {"c", "compiler-default", "compiler-default", "compiler-default", null})) {
            BitcodeManifest.ArtifactRecord record = languageContext(
                    current.records().getFirst(), context[0], context[1], context[2], context[3], context[4]);
            BitcodeManifestValidator.validate(BitcodeTestFixtures.manifest(List.of(record)), 10, 100);
        }
    }

    @Test
    void isolatesUnsupportedLanguageStandardAsFailedRecord() {
        BitcodeManifest.ArtifactRecord failed = languageContext(
                BitcodeTestFixtures.failed("unsupported", "src/unsupported.c"),
                "c", "unsupported", "iso", "explicit", "-std=c2x-draft");
        BitcodeManifestValidator.validate(BitcodeTestFixtures.manifest(List.of(failed)), 10, 100);

        BitcodeManifest.ArtifactRecord produced = languageContext(
                BitcodeTestFixtures.produced("unsupported", "src/unsupported.c", 8, BitcodeTestFixtures.HASH_A),
                "c", "unsupported", "iso", "explicit", "-std=c2x-draft");
        assertInvalid(BitcodeTestFixtures.manifest(List.of(produced)));
    }

    @Test
    void rejectsInconsistentLanguageStandardContexts() {
        BitcodeManifest.ArtifactRecord record = valid().records().getFirst();
        for (BitcodeManifest.ArtifactRecord invalid : List.of(
                languageContext(record, "c", "c++17", "iso", "explicit", "-std=c++17"),
                languageContext(record, "c", "c17", "iso", "explicit", null),
                languageContext(record, "c", "compiler-default", "compiler-default", "compiler-default",
                        "-std=c17"),
                languageContext(record, "c", "c17", "iso", "compiler-default", null))) {
            assertInvalid(BitcodeTestFixtures.manifest(List.of(invalid)));
        }
    }

    @Test
    void rejectsSchemaIdentityAndAggregateTampering() {
        BitcodeManifest valid = valid();
        assertInvalid(null);
        assertInvalid(copy(valid, "WrongKind", valid.schemaVersion(), valid.artifactSetId(), valid.counts(),
                valid.records(), valid.scopes(), valid.semanticDigest()));
        assertInvalid(copy(valid, valid.kind(), "1.0", valid.artifactSetId(), valid.counts(),
                valid.records(), valid.scopes(), valid.semanticDigest()));
        assertInvalid(copy(valid, valid.kind(), valid.schemaVersion(), "bad", valid.counts(),
                valid.records(), valid.scopes(), valid.semanticDigest()));
        assertInvalid(copy(valid, valid.kind(), valid.schemaVersion(), BitcodeTestFixtures.HASH_B, valid.counts(),
                valid.records(), valid.scopes(), valid.semanticDigest()));
        assertInvalid(copy(valid, valid.kind(), valid.schemaVersion(), valid.artifactSetId(),
                new BitcodeManifest.Counts(1, 2, 1, 0, 0, 8), valid.records(), valid.scopes(),
                valid.semanticDigest()));
        assertInvalid(copy(valid, valid.kind(), valid.schemaVersion(), valid.artifactSetId(), valid.counts(),
                valid.records(), valid.scopes(), BitcodeTestFixtures.HASH_B));
        assertThatThrownBy(() -> BitcodeManifestValidator.validate(valid, 0, 100))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> BitcodeManifestValidator.validate(valid, 10, 4))
                .isInstanceOf(IllegalArgumentException.class);
        assertInvalid(new BitcodeManifest(valid.kind(), valid.schemaVersion(), valid.artifactSetId(),
                valid.sourceIdentityDigest(), null, valid.producer(), valid.status(), valid.counts(),
                valid.records(), valid.scopes(), valid.generatedAt(), valid.semanticDigest()));
        assertInvalid(new BitcodeManifest(valid.kind(), valid.schemaVersion(), valid.artifactSetId(),
                valid.sourceIdentityDigest(), new BitcodeManifest.CompileContext("bad", BitcodeTestFixtures.HASH_A),
                valid.producer(), valid.status(), valid.counts(), valid.records(), valid.scopes(),
                valid.generatedAt(), valid.semanticDigest()));
        assertInvalid(new BitcodeManifest(valid.kind(), valid.schemaVersion(), valid.artifactSetId(),
                valid.sourceIdentityDigest(), valid.compileContext(), null, valid.status(), valid.counts(),
                valid.records(), valid.scopes(), valid.generatedAt(), valid.semanticDigest()));
        assertInvalid(new BitcodeManifest(valid.kind(), valid.schemaVersion(), valid.artifactSetId(),
                valid.sourceIdentityDigest(), valid.compileContext(), valid.producer(), valid.status(), null,
                valid.records(), valid.scopes(), valid.generatedAt(), valid.semanticDigest()));
        assertInvalid(new BitcodeManifest(valid.kind(), valid.schemaVersion(), valid.artifactSetId(),
                valid.sourceIdentityDigest(), valid.compileContext(), valid.producer(), valid.status(),
                valid.counts(), null, valid.scopes(), valid.generatedAt(), valid.semanticDigest()));
        assertInvalid(new BitcodeManifest(valid.kind(), valid.schemaVersion(), valid.artifactSetId(),
                valid.sourceIdentityDigest(), valid.compileContext(), valid.producer(), valid.status(),
                valid.counts(), valid.records(), null, valid.generatedAt(), valid.semanticDigest()));
        assertInvalid(new BitcodeManifest(valid.kind(), valid.schemaVersion(), valid.artifactSetId(),
                valid.sourceIdentityDigest(), valid.compileContext(), valid.producer(), valid.status(),
                valid.counts(), List.of(valid.records().getFirst(), valid.records().getFirst()), valid.scopes(),
                valid.generatedAt(), valid.semanticDigest()));
    }

    @Test
    void rejectsMalformedRecordsCapabilitiesAndDiagnostics() {
        BitcodeManifest valid = valid();
        BitcodeManifest.ArtifactRecord record = valid.records().getFirst();
        assertInvalid(withRecords(valid, List.of(copyRecord(record, "bad", record.status(), record.diagnostic(),
                record.bitcode(), record.capabilities(), record.sidecars()))));
        assertInvalid(withRecords(valid, List.of(copyRecord(record, record.recordId(), "unknown", null,
                record.bitcode(), record.capabilities(), record.sidecars()))));
        assertInvalid(withRecords(valid, List.of(copyRecord(record, record.recordId(), "produced",
                new BitcodeManifest.Diagnostic("X", "中", "en", "修", "fix"), record.bitcode(),
                record.capabilities(), record.sidecars()))));
        assertInvalid(withRecords(valid, List.of(copyRecord(record, record.recordId(), "produced", null,
                null, record.capabilities(), record.sidecars()))));
        assertInvalid(withRecords(valid, List.of(copyRecord(record, record.recordId(), "produced", null,
                new BitcodeManifest.Bitcode("../escape.bc", 8, BitcodeTestFixtures.HASH_A),
                record.capabilities(), record.sidecars()))));
        assertInvalid(withRecords(valid, List.of(copyRecord(record, record.recordId(), "produced", null,
                record.bitcode(), List.of("llvm.ir-readable"), record.sidecars()))));
        BitcodeManifest.ArtifactRecord failed = BitcodeTestFixtures.failed("x", "src/x.c");
        assertInvalid(withRecords(BitcodeTestFixtures.manifest(List.of(failed)), List.of(
                copyRecord(failed, failed.recordId(), "failed", null, null,
                        failed.capabilities(), failed.sidecars()))));

        for (Consumer<ObjectNode> mutation : List.<Consumer<ObjectNode>>of(
                node -> node.putNull("profile"),
                node -> node.withObject("profile").put("name", "unknown"),
                node -> node.withObject("profile").put("version", " "),
                node -> node.put("artifact_key", BitcodeTestFixtures.HASH_B),
                node -> node.put("semantic_digest", BitcodeTestFixtures.HASH_B),
                node -> node.putNull("source"),
                node -> node.putNull("production_compiler"),
                node -> node.putNull("producer"),
                node -> node.putNull("target"),
                node -> node.putNull("input_digests"),
                node -> node.putNull("provenance"),
                node -> node.putNull("capabilities"),
                node -> node.putNull("sidecars"),
                node -> node.put("language", " "),
                node -> node.put("standard", " "),
                node -> node.put("optimization", " "),
                node -> node.put("debug", " "),
                node -> node.put("module_kind", "linked-module"),
                node -> node.withObject("target").put("triple", " "),
                node -> node.withObject("target").put("data_layout", " "),
                node -> node.withObject("target").putNull("abi"))) {
            assertInvalid(withRecords(valid, List.of(mutateRecord(record, mutation, false))));
        }

        for (Consumer<ObjectNode> mutation : List.<Consumer<ObjectNode>>of(
                node -> node.withObject("source").put("path", "../outside.c"),
                node -> node.withObject("source").put("sha256", "bad"),
                node -> node.put("compile_record_digest", "bad"),
                node -> node.withObject("input_digests").put("../header.h", BitcodeTestFixtures.HASH_A),
                node -> node.withObject("producer").put("host_triple", " "))) {
            assertInvalid(withRecords(valid, List.of(mutateRecord(record, mutation, true))));
        }
        for (String producerField : List.of("family", "version", "llvm_version")) {
            assertInvalid(withRecords(valid, List.of(mutateRecord(record,
                    node -> node.withObject("producer").put(producerField, " "), true))));
        }
        assertInvalid(withRecords(valid, List.of(mutateRecord(record,
                node -> node.withObject("source").putNull("sha256"), true))));

        BitcodeManifest.ArtifactRecord buildFaithful = mutateRecord(record,
                node -> node.withObject("profile").put("name", "build-faithful"), true);
        BitcodeManifestValidator.validate(BitcodeTestFixtures.manifest(List.of(buildFaithful)), 10, 100);

        BitcodeManifest failedManifest = BitcodeTestFixtures.manifest(List.of(failed));
        for (Consumer<ObjectNode> mutation : List.<Consumer<ObjectNode>>of(
                node -> node.put("bitcode", mapper.valueToTree(record.bitcode())),
                node -> node.withObject("diagnostic").put("code", " "),
                node -> node.withObject("diagnostic").putNull("detail"),
                node -> node.withObject("diagnostic").putNull("detail_en"))) {
            assertInvalid(withRecords(failedManifest, List.of(mutateRecord(failed, mutation, true))));
        }
    }

    @Test
    void rejectsDuplicateRecordsPathsSidecarsAndInvalidScopes() {
        BitcodeManifest.ArtifactRecord record = BitcodeTestFixtures.produced(
                "a", "src/a.c", 8, BitcodeTestFixtures.HASH_A);
        BitcodeManifest duplicate = BitcodeTestFixtures.manifest(List.of(record, record));
        assertInvalid(duplicate);

        BitcodeManifest.ArtifactRecord alias = BitcodeTestFixtures.produced(
                "alias", "src/alias.c", 8, BitcodeTestFixtures.HASH_A);
        alias = mutateRecord(alias, node -> node.put("artifact_key", record.artifactKey()), false);
        assertInvalid(BitcodeTestFixtures.manifest(List.of(record, alias)));

        BitcodeManifest valid = BitcodeTestFixtures.manifest(List.of(record));
        BitcodeManifest.Sidecar sidecar = new BitcodeManifest.Sidecar(
                "symbol-index", "1", "bitcode/" + record.recordId() + ".bc", 1,
                BitcodeTestFixtures.HASH_A, List.of("symbols.linkage"));
        assertInvalid(withRecords(valid, List.of(copyRecord(record, record.recordId(), record.status(), null,
                record.bitcode(), record.capabilities(), List.of(sidecar)))));

        BitcodeManifest.Scope scope = valid.scopes().getFirst();
        BitcodeManifest.Scope uncovered = new BitcodeManifest.Scope(scope.scopeId(), scope.targetId(),
                List.of(BitcodeTestFixtures.HASH_B), scope.evidence(), false, scope.externalBoundaries(),
                scope.targetTriple(), scope.semanticDigest());
        assertInvalid(copy(valid, valid.kind(), valid.schemaVersion(), valid.artifactSetId(), valid.counts(),
                valid.records(), List.of(uncovered), valid.semanticDigest()));
        assertInvalid(copy(valid, valid.kind(), valid.schemaVersion(), valid.artifactSetId(), valid.counts(),
                valid.records(), List.of(), valid.semanticDigest()));

        for (BitcodeManifest.Sidecar malformed : List.of(
                new BitcodeManifest.Sidecar("", "1", "sidecars/a.json", 1,
                        BitcodeTestFixtures.HASH_A, List.of()),
                new BitcodeManifest.Sidecar("symbols", "", "sidecars/a.json", 1,
                        BitcodeTestFixtures.HASH_A, List.of()),
                new BitcodeManifest.Sidecar("symbols", "1", "../a.json", 1,
                        BitcodeTestFixtures.HASH_A, List.of()),
                new BitcodeManifest.Sidecar("symbols", "1", "sidecars/a.json", -1,
                        BitcodeTestFixtures.HASH_A, List.of()),
                new BitcodeManifest.Sidecar("symbols", "1", "sidecars/a.json", 1,
                        "bad", List.of()))) {
            BitcodeManifest.ArtifactRecord withSidecar = mutateRecord(record,
                    node -> node.set("sidecars", mapper.valueToTree(List.of(malformed))), true);
            assertInvalid(BitcodeTestFixtures.manifest(List.of(withSidecar)));
        }

        BitcodeManifest.ArtifactRecord tiny = mutateRecord(record,
                node -> node.withObject("bitcode").put("bytes", 3), true);
        assertInvalid(BitcodeTestFixtures.manifest(List.of(tiny)));
        BitcodeManifest.ArtifactRecord duplicatePath = BitcodeTestFixtures.produced(
                "b", "src/b.c", 8, BitcodeTestFixtures.HASH_A);
        duplicatePath = mutateRecord(duplicatePath,
                node -> node.withObject("bitcode").put("path", record.bitcode().path()), true);
        assertInvalid(BitcodeTestFixtures.manifest(List.of(record, duplicatePath)));

        for (BitcodeManifest.Counts counts : List.of(
                new BitcodeManifest.Counts(2, 1, 1, 0, 0, 8),
                new BitcodeManifest.Counts(1, -1, 1, 0, 0, 8),
                new BitcodeManifest.Counts(1, 2, 1, 0, 0, 8),
                new BitcodeManifest.Counts(1, 1, 0, 0, 1, 8),
                new BitcodeManifest.Counts(1, 1, 1, 1, 0, 8),
                new BitcodeManifest.Counts(1, 1, 1, 0, 1, 8),
                new BitcodeManifest.Counts(1, 1, 1, 0, 0, 7))) {
            assertInvalid(copy(valid, valid.kind(), valid.schemaVersion(), valid.artifactSetId(), counts,
                    valid.records(), valid.scopes(), valid.semanticDigest()));
        }
    }

    @Test
    void rejectsEveryInvalidScopeShapeAndIdentity() {
        BitcodeManifest valid = valid();
        BitcodeManifest.Scope scope = valid.scopes().getFirst();
        List<BitcodeManifest.Scope> invalidScopes = List.of(
                scope(scope, "bad", scope.targetId(), scope.recordIds(), scope.evidence(),
                        scope.externalBoundaries(), scope.targetTriple(), scope.semanticDigest()),
                scope(scope, scope.scopeId(), "bad", scope.recordIds(), scope.evidence(),
                        scope.externalBoundaries(), scope.targetTriple(), scope.semanticDigest()),
                scope(scope, scope.scopeId(), scope.targetId(), null, scope.evidence(),
                        scope.externalBoundaries(), scope.targetTriple(), scope.semanticDigest()),
                scope(scope, scope.scopeId(), scope.targetId(), List.of(), scope.evidence(),
                        scope.externalBoundaries(), scope.targetTriple(), scope.semanticDigest()),
                scope(scope, scope.scopeId(), scope.targetId(), List.of(scope.recordIds().getFirst(),
                        scope.recordIds().getFirst()), scope.evidence(), scope.externalBoundaries(),
                        scope.targetTriple(), scope.semanticDigest()),
                scope(scope, scope.scopeId(), scope.targetId(), scope.recordIds(), " ",
                        scope.externalBoundaries(), scope.targetTriple(), scope.semanticDigest()),
                scope(scope, scope.scopeId(), scope.targetId(), scope.recordIds(), scope.evidence(),
                        null, scope.targetTriple(), scope.semanticDigest()),
                scope(scope, scope.scopeId(), scope.targetId(), scope.recordIds(), scope.evidence(),
                        scope.externalBoundaries(), " ", scope.semanticDigest()),
                scope(scope, scope.scopeId(), scope.targetId(), scope.recordIds(), scope.evidence(),
                        scope.externalBoundaries(), scope.targetTriple(), BitcodeTestFixtures.HASH_B),
                scope(scope, BitcodeTestFixtures.HASH_B, scope.targetId(), scope.recordIds(), scope.evidence(),
                        scope.externalBoundaries(), scope.targetTriple(), scope.semanticDigest()));
        for (BitcodeManifest.Scope invalid : invalidScopes) {
            assertInvalid(copy(valid, valid.kind(), valid.schemaVersion(), valid.artifactSetId(), valid.counts(),
                    valid.records(), List.of(invalid), valid.semanticDigest()));
        }

        BitcodeManifest.ArtifactRecord second = BitcodeTestFixtures.produced(
                "second", "src/second.c", 8, BitcodeTestFixtures.HASH_A);
        BitcodeManifest twoRecords = BitcodeTestFixtures.manifest(List.of(valid.records().getFirst(), second));
        assertInvalid(copy(twoRecords, twoRecords.kind(), twoRecords.schemaVersion(), twoRecords.artifactSetId(),
                twoRecords.counts(), twoRecords.records(), valid.scopes(), twoRecords.semanticDigest()));
    }

    @Test
    void validatesStrictPosixRelativePathsAndCanonicalIdentity() {
        BitcodeManifestValidator.validateSafeRelativePath("src/目录/a.cpp", "source");
        for (String path : List.of("../secret", "/etc/passwd", "C:/secret", "a\\b", "a/../b", "", "a\0b")) {
            assertThatThrownBy(() -> BitcodeManifestValidator.validateSafeRelativePath(path, "source"))
                    .isInstanceOf(IllegalArgumentException.class);
        }
        assertThat(BitcodeCanonicalIdentity.digest(Map.of("b", 2, "a", List.of("乙", "甲"))))
                .isEqualTo(BitcodeCanonicalIdentity.digest(Map.of("a", List.of("甲", "乙"), "b", 2)));
        assertThat(BitcodeCanonicalIdentity.digest(Map.of("stable", 1, "generated_at", "a"), "generated_at"))
                .isEqualTo(BitcodeCanonicalIdentity.digest(Map.of("stable", 1, "generated_at", "b"), "generated_at"));
        assertThat(BitcodeCanonicalIdentity.digest(Map.of(
                "path", "src/目录/a.c",
                "profile", Map.of("name", "source-preserving", "version", "1"),
                "capabilities", List.of("memory.fence", "fp.operations"))))
                .isEqualTo("4f3fa09da25853b5937198db216e813fbec940151f6f146fef0c0e575ed275ce");
    }

    @Test
    void unavailableSummaryAndLegacyShapeAreExplicit() {
        BitcodeSummary summary = BitcodeSummary.unavailable(BitcodeStatus.NOT_ATTEMPTED,
                BitcodeReasonCode.LEGACY_RECORD);
        assertThat(summary.toMap()).containsEntry("available", false)
                .containsEntry("legacy", true)
                .containsEntry("schemaVersion", BitcodeManifest.SCHEMA_VERSION)
                .containsEntry("sourceIdentityDigest", null);
    }

    private BitcodeManifest valid() {
        return BitcodeTestFixtures.manifest(List.of(BitcodeTestFixtures.produced(
                "a", "src/a.c", 8, BitcodeTestFixtures.HASH_A)));
    }

    private void assertInvalid(BitcodeManifest manifest) {
        assertThatThrownBy(() -> BitcodeManifestValidator.validate(manifest, 10, 100))
                .isInstanceOf(IllegalArgumentException.class);
    }

    private BitcodeManifest withRecords(BitcodeManifest original, List<BitcodeManifest.ArtifactRecord> records) {
        BitcodeManifest generated = BitcodeTestFixtures.manifest(records);
        return generated;
    }

    private BitcodeManifest copy(BitcodeManifest value, String kind, String schema, String id,
                                 BitcodeManifest.Counts counts,
                                 List<BitcodeManifest.ArtifactRecord> records,
                                 List<BitcodeManifest.Scope> scopes, String semantic) {
        return new BitcodeManifest(kind, schema, id, value.sourceIdentityDigest(), value.compileContext(),
                value.producer(), value.status(), counts, records, scopes, value.generatedAt(), semantic);
    }

    private BitcodeManifest.ArtifactRecord copyRecord(BitcodeManifest.ArtifactRecord value, String recordId,
                                                      String status, BitcodeManifest.Diagnostic diagnostic,
                                                      BitcodeManifest.Bitcode bitcode, List<String> capabilities,
                                                      List<BitcodeManifest.Sidecar> sidecars) {
        return new BitcodeManifest.ArtifactRecord(recordId, value.physicalTuId(), value.contextId(),
                value.artifactKey(), value.profile(), status, diagnostic, bitcode, value.productionCompiler(),
                value.producer(), value.target(), value.language(), value.standard(), value.dialect(),
                value.standardSource(), value.standardOption(), value.optimization(), value.debug(),
                value.moduleKind(), value.source(), value.compileRecordDigest(),
                value.inputDigests(), value.provenance(), capabilities, sidecars, value.semanticDigest());
    }

    private BitcodeManifest.ArtifactRecord mutateRecord(BitcodeManifest.ArtifactRecord value,
                                                        Consumer<ObjectNode> mutation,
                                                        boolean reidentify) {
        ObjectNode node = mapper.valueToTree(value);
        mutation.accept(node);
        try {
            BitcodeManifest.ArtifactRecord mutated = mapper.treeToValue(node, BitcodeManifest.ArtifactRecord.class);
            return reidentify ? BitcodeTestFixtures.reidentify(mutated) : mutated;
        } catch (Exception ex) {
            throw new AssertionError(ex);
        }
    }

    private BitcodeManifest.ArtifactRecord languageContext(BitcodeManifest.ArtifactRecord value,
                                                            String language, String standard, String dialect,
                                                            String standardSource, String standardOption) {
        return mutateRecord(value, node -> {
            node.put("language", language);
            node.put("standard", standard);
            node.put("dialect", dialect);
            node.put("standard_source", standardSource);
            if (standardOption == null) {
                node.putNull("standard_option");
            } else {
                node.put("standard_option", standardOption);
            }
        }, true);
    }

    private BitcodeManifest reidentifyManifest(BitcodeManifest value) {
        String semantic = BitcodeCanonicalIdentity.digest(value,
                "semantic_digest", "generated_at", "artifact_set_id", "raw_compile_commands_sha256");
        BitcodeManifest withSemantic = copy(value, value.kind(), value.schemaVersion(), value.artifactSetId(),
                value.counts(), value.records(), value.scopes(), semantic);
        String identity = BitcodeCanonicalIdentity.digest(withSemantic,
                "artifact_set_id", "semantic_digest", "generated_at", "diagnostic",
                "raw_compile_commands_sha256");
        return copy(withSemantic, withSemantic.kind(), withSemantic.schemaVersion(), identity,
                withSemantic.counts(), withSemantic.records(), withSemantic.scopes(), semantic);
    }

    private BitcodeManifest.Scope scope(BitcodeManifest.Scope value, String scopeId, String targetId,
                                        List<String> recordIds, String evidence, List<String> boundaries,
                                        String triple, String semantic) {
        return new BitcodeManifest.Scope(scopeId, targetId, recordIds, evidence, value.closed(), boundaries,
                triple, semantic);
    }
}
