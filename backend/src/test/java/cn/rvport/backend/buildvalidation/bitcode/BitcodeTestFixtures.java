package cn.rvport.backend.buildvalidation.bitcode;

import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

final class BitcodeTestFixtures {

    static final String HASH_A = "a".repeat(64);
    static final String HASH_B = "b".repeat(64);
    static final List<String> CAPABILITIES = List.of(
            "debug.locations", "debug.variables", "fp.fast-math-flags", "fp.operations",
            "llvm.ir-readable", "memory.atomic-ordering", "memory.fence", "memory.syncscope",
            "source.correlation", "symbols.linkage", "target.data-layout", "target.triple");

    private BitcodeTestFixtures() {
    }

    static BitcodeManifest manifest(List<BitcodeManifest.ArtifactRecord> records) {
        List<BitcodeManifest.ArtifactRecord> sorted = records.stream()
                .sorted(java.util.Comparator.comparing(BitcodeManifest.ArtifactRecord::recordId)).toList();
        List<BitcodeManifest.Scope> scopes = List.of(scope(sorted));
        int produced = (int) sorted.stream().filter(record -> "produced".equals(record.status())).count();
        int missing = (int) sorted.stream().filter(record -> "missing".equals(record.status())).count();
        int failed = sorted.size() - produced - missing;
        long bytes = sorted.stream().filter(record -> record.bitcode() != null)
                .mapToLong(record -> record.bitcode().bytes()).sum();
        BitcodeManifest base = new BitcodeManifest(
                BitcodeManifest.KIND, BitcodeManifest.SCHEMA_VERSION, HASH_A, HASH_B,
                new BitcodeManifest.CompileContext(HASH_A, HASH_B), producer(),
                produced == sorted.size() ? "READY" : produced > 0 ? "PARTIAL" : "FAILED",
                new BitcodeManifest.Counts(sorted.size(), sorted.size(), produced, missing, failed, bytes),
                sorted, scopes, Instant.parse("2026-01-01T00:00:00Z"), HASH_A);
        String semantic = BitcodeCanonicalIdentity.digest(base,
                "semantic_digest", "generated_at", "artifact_set_id", "raw_compile_commands_sha256");
        BitcodeManifest withSemantic = copy(base, HASH_A, semantic);
        String identity = BitcodeCanonicalIdentity.digest(withSemantic,
                "artifact_set_id", "semantic_digest", "generated_at", "diagnostic",
                "raw_compile_commands_sha256");
        return copy(withSemantic, identity, semantic);
    }

    static BitcodeManifest.ArtifactRecord produced(String seed, String path, long bytes, String sha) {
        return record(seed, path, "produced", new BitcodeManifest.Bitcode("bitcode/" + seed + ".bc", bytes, sha), null);
    }

    static BitcodeManifest.ArtifactRecord failed(String seed, String path) {
        return record(seed, path, "failed", null, new BitcodeManifest.Diagnostic(
                "TRANSLATION_UNIT_FAILED", "编译失败", "Compilation failed", "检查参数", "Check arguments"));
    }

    static BitcodeManifest.ArtifactRecord missing(String seed, String path) {
        return record(seed, path, "missing", null, new BitcodeManifest.Diagnostic(
                "DUPLICATE_CONTEXT", "重复上下文", "Duplicate context", "检查参数", "Check arguments"));
    }

    static BitcodeManifest.ArtifactRecord reidentify(BitcodeManifest.ArtifactRecord value) {
        String recordId = BitcodeCanonicalIdentity.digest(Map.of(
                "context_id", value.contextId(), "profile", value.profile()));
        BitcodeManifest.ArtifactRecord withRecordId = new BitcodeManifest.ArtifactRecord(
                recordId, value.physicalTuId(), value.contextId(), value.artifactKey(), value.profile(),
                value.status(), value.diagnostic(), value.bitcode(), value.productionCompiler(), value.producer(),
                value.target(), value.language(), value.standard(), value.dialect(), value.standardSource(),
                value.standardOption(), value.optimization(), value.debug(),
                value.moduleKind(), value.source(), value.compileRecordDigest(), value.inputDigests(),
                value.provenance(), value.capabilities(), value.sidecars(), value.semanticDigest());
        Map<String, Object> artifactIdentity = new LinkedHashMap<>();
        artifactIdentity.put("context_id", withRecordId.contextId());
        artifactIdentity.put("profile", withRecordId.profile());
        artifactIdentity.put("producer", withRecordId.producer());
        artifactIdentity.put("bitcode_sha256",
                withRecordId.bitcode() == null ? null : withRecordId.bitcode().sha256());
        String artifactKey = BitcodeCanonicalIdentity.digest(artifactIdentity);
        BitcodeManifest.ArtifactRecord withArtifactKey = copy(withRecordId, artifactKey, HASH_A);
        String semantic = BitcodeCanonicalIdentity.digest(
                withArtifactKey, "semantic_digest", "artifact_key", "diagnostic");
        return copy(withArtifactKey, artifactKey, semantic);
    }

    static BitcodeManifest.ArtifactRecord record(String seed, String path, String status,
                                                  BitcodeManifest.Bitcode bitcode,
                                                  BitcodeManifest.Diagnostic diagnostic) {
        String contextId = sha(seed + "-context");
        String identity = BitcodeCanonicalIdentity.digest(Map.of("context_id", contextId, "profile",
                new BitcodeManifest.Profile("source-preserving", "1")));
        BitcodeManifest.ArtifactRecord base = new BitcodeManifest.ArtifactRecord(
                identity, sha(seed), contextId, HASH_A,
                new BitcodeManifest.Profile("source-preserving", "1"), status, diagnostic, bitcode,
                new BitcodeManifest.Compiler("gcc", "gcc", "gcc 12"), producer(), target(),
                "c", "c17", "iso", "explicit", "-std=c17",
                "O0", "full", "translation-unit",
                new BitcodeManifest.Source(path, sha(path)), sha(seed + "-compile"),
                Map.of(path, sha(path)), new BitcodeManifest.Provenance("partial", List.of("headers unavailable")),
                CAPABILITIES, List.of(), HASH_A);
        String semantic = BitcodeCanonicalIdentity.digest(base, "semantic_digest", "artifact_key", "diagnostic");
        Map<String, Object> artifactIdentity = new LinkedHashMap<>();
        artifactIdentity.put("context_id", base.contextId());
        artifactIdentity.put("profile", base.profile());
        artifactIdentity.put("producer", base.producer());
        artifactIdentity.put("bitcode_sha256", bitcode == null ? null : bitcode.sha256());
        String artifactKey = BitcodeCanonicalIdentity.digest(artifactIdentity);
        return copy(base, artifactKey, semantic);
    }

    static BitcodeManifest.Producer producer() {
        return new BitcodeManifest.Producer("clang", "21.1.8", "21.1.8", "x86_64-linux-gnu");
    }

    static BitcodeManifest.Target target() {
        return new BitcodeManifest.Target("x86_64-linux-gnu", "e-p:64:64",
                Map.of("architecture", "x86_64", "pointer_width", 64, "endianness", "little"));
    }

    static String sha(String value) {
        try {
            return java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(java.nio.charset.StandardCharsets.UTF_8)));
        } catch (java.security.NoSuchAlgorithmException ex) {
            throw new IllegalStateException(ex);
        }
    }

    private static BitcodeManifest.Scope scope(List<BitcodeManifest.ArtifactRecord> records) {
        List<String> ids = records.stream().map(BitcodeManifest.ArtifactRecord::recordId).sorted().toList();
        BitcodeManifest.Scope base = new BitcodeManifest.Scope(HASH_A, sha("target"), ids,
                "compile-database-planned-set", false, List.of("unknown-external-boundary"),
                "x86_64-linux-gnu", HASH_A);
        String semantic = BitcodeCanonicalIdentity.digest(base, "semantic_digest", "scope_id");
        String id = BitcodeCanonicalIdentity.digest(Map.of(
                "target_id", base.targetId(), "record_ids", ids, "closed", false,
                "semantic_digest", semantic));
        return new BitcodeManifest.Scope(id, base.targetId(), ids, base.evidence(), base.closed(),
                base.externalBoundaries(), base.targetTriple(), semantic);
    }

    private static BitcodeManifest copy(BitcodeManifest value, String id, String semantic) {
        return new BitcodeManifest(value.kind(), value.schemaVersion(), id, value.sourceIdentityDigest(),
                value.compileContext(), value.producer(), value.status(), value.counts(), value.records(),
                value.scopes(), value.generatedAt(), semantic);
    }

    private static BitcodeManifest.ArtifactRecord copy(BitcodeManifest.ArtifactRecord value,
                                                       String artifactKey, String semantic) {
        return new BitcodeManifest.ArtifactRecord(value.recordId(), value.physicalTuId(), value.contextId(),
                artifactKey, value.profile(), value.status(), value.diagnostic(), value.bitcode(),
                value.productionCompiler(), value.producer(), value.target(), value.language(), value.standard(),
                value.dialect(), value.standardSource(), value.standardOption(), value.optimization(), value.debug(),
                value.moduleKind(), value.source(), value.compileRecordDigest(),
                value.inputDigests(), value.provenance(), value.capabilities(), value.sidecars(), semantic);
    }
}
