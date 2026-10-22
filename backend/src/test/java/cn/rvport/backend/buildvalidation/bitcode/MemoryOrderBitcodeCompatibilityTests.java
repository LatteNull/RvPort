package cn.rvport.backend.buildvalidation.bitcode;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.InputStream;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class MemoryOrderBitcodeCompatibilityTests {

    private final ObjectMapper mapper = new ObjectMapper().findAndRegisterModules();

    @Test
    void v2FixtureMapsEveryRealMemoryOrderExternalContractFieldWithoutInternalArtifactKey() throws Exception {
        BitcodeManifest manifest = BitcodeTestFixtures.manifest(List.of(
                BitcodeTestFixtures.produced("ok", "src/atomic.c", 8, BitcodeTestFixtures.HASH_A),
                BitcodeTestFixtures.failed("failed", "src/fence.c")));
        JsonNode required = resource("bitcode/memory-order-external-required-fields.json");

        List<Map<String, Object>> records = manifest.records().stream().map(this::mapRecord).toList();
        Map<String, Object> bundle = mapBundle(manifest, records);

        assertThat(bundle.keySet()).containsAll(strings(required.get("bundle_required")));
        assertThat(records).allSatisfy(record -> {
            assertThat(record.keySet()).containsAll(strings(required.get("record_required")));
            assertThat(record).doesNotContainKeys("artifact_key", "context_id", "project_id", "build_run_id");
        });
        assertThat((List<Map<String, Object>>) bundle.get("scopes")).allSatisfy(scope ->
                assertThat(scope.keySet()).containsAll(strings(required.get("scope_required"))));
        assertThat(records).extracting(record -> record.get("status"))
                .containsExactlyInAnyOrder("produced", "failed");
        assertThat((Map<String, Object>) records.getFirst().get("producer")).containsKeys(
                "family", "version", "llvm_version", "host_triple");
        assertThat((Map<String, Object>) records.getFirst().get("target"))
                .containsKeys("triple", "data_layout", "abi");
    }

    @Test
    void canonicalFixtureIsSharedByJavaAndPythonImplementations() throws Exception {
        JsonNode vector = resource("bitcode/canonical-identity-vector.json");
        assertThat(BitcodeCanonicalIdentity.digest(mapper.convertValue(vector.get("input"), Object.class)))
                .isEqualTo(vector.get("sha256").asText());
    }

    private Map<String, Object> mapRecord(BitcodeManifest.ArtifactRecord record) {
        Map<String, Object> result = envelope("ExternalBitcodeArtifactRecord");
        result.put("record_id", record.recordId());
        result.put("physical_tu_id", record.physicalTuId());
        result.put("status", record.status());
        result.put("diagnostic", record.diagnostic() == null ? null : Map.of(
                "code", record.diagnostic().code(), "detail", record.diagnostic().detail(),
                "detail_en", record.diagnostic().detailEn(), "suggestion", record.diagnostic().suggestion(),
                "suggestion_en", record.diagnostic().suggestionEn(), "relevant", true,
                "record_id", record.recordId(), "references", List.of()));
        result.put("bitcode", record.bitcode() == null ? null : Map.of(
                "path", record.bitcode().path(), "sha256", record.bitcode().sha256(),
                "bytes", record.bitcode().bytes()));
        result.put("producer", mapper.convertValue(record.producer(), Map.class));
        result.put("target", mapper.convertValue(record.target(), Map.class));
        result.put("language", record.language());
        result.put("standard", record.standard());
        result.put("optimization", record.optimization());
        result.put("debug", record.debug());
        result.put("module_kind", record.moduleKind());
        result.put("source", mapper.convertValue(record.source(), Map.class));
        result.put("compile_record_digest", record.compileRecordDigest());
        result.put("input_digests", record.inputDigests());
        result.put("semantic_digest", externalDigest(result));
        return result;
    }

    private Map<String, Object> mapBundle(BitcodeManifest manifest, List<Map<String, Object>> records) {
        Map<String, Object> result = envelope("ExternalBitcodeBundleManifest");
        result.put("bundle_id", manifest.artifactSetId());
        result.put("producer", mapper.convertValue(manifest.producer(), Map.class));
        result.put("records", records.stream().map(record -> Map.<String, Object>of(
                "path", "records/" + record.get("record_id") + ".json",
                "sha256", BitcodeCanonicalIdentity.digest(record))).toList());
        result.put("scopes", manifest.scopes().stream().map(scope -> Map.<String, Object>of(
                "target_id", scope.targetId(), "record_ids", scope.recordIds(), "evidence", scope.evidence(),
                "closed", scope.closed(), "external_boundaries", scope.externalBoundaries(),
                "target_triple", scope.targetTriple())).toList());
        result.put("budgets", Map.of("max_records", 10000, "max_artifact_bytes", 1073741824,
                "max_total_bytes", 8589934592L, "max_worker_seconds", 120, "max_output_bytes", 16777216));
        result.put("semantic_digest", externalDigest(result));
        return result;
    }

    private Map<String, Object> envelope(String kind) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("schema_version", 1);
        result.put("kind", kind);
        result.put("ingestion_version", "0.1.0");
        result.put("policy_id", "external-bitcode-ingestion-v1");
        return result;
    }

    private String externalDigest(Map<String, Object> value) {
        Map<String, Object> copy = new LinkedHashMap<>(value);
        copy.remove("semantic_digest");
        return BitcodeCanonicalIdentity.digest(copy);
    }

    private JsonNode resource(String path) throws Exception {
        try (InputStream input = getClass().getClassLoader().getResourceAsStream(path)) {
            return mapper.readTree(java.util.Objects.requireNonNull(input));
        }
    }

    private List<String> strings(JsonNode array) {
        return java.util.stream.StreamSupport.stream(array.spliterator(), false).map(JsonNode::asText).toList();
    }
}
