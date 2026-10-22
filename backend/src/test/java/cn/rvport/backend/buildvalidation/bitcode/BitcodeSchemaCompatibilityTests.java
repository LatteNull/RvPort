package cn.rvport.backend.buildvalidation.bitcode;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.List;
import org.apache.commons.compress.archivers.tar.TarArchiveEntry;
import org.apache.commons.compress.archivers.tar.TarArchiveOutputStream;
import org.apache.commons.compress.compressors.gzip.GzipCompressorOutputStream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class BitcodeSchemaCompatibilityTests {

    private final ObjectMapper mapper = new ObjectMapper().findAndRegisterModules();
    @TempDir Path tempDir;

    @Test
    void acceptsTheRealSchema20VectorWithoutInjecting21NullFields() throws Exception {
        JsonNode raw = mapper.readTree(getClass().getResourceAsStream(
                "/bitcode/evidence-repair-schema-2.0.json"));
        BitcodeManifest manifest = mapper.treeToValue(raw, BitcodeManifest.class);

        BitcodeManifestValidator.validate(manifest, raw, 20, 1_000_000);

        assertThat(raw.path("records").get(0).has("dialect")).isFalse();
        assertThat(manifest.records().get(0).dialect()).isNull();
        assertThat(manifest.producer().llvmVersion()).isEqualTo("21.1.8");
    }

    @Test
    void validates21AndRejectsLegacyNullsMissingFieldsUnknownVersionsAndTampering() throws Exception {
        BitcodeManifest current = manifestFor("valid bundle".getBytes(StandardCharsets.UTF_8));
        JsonNode currentRaw = mapper.valueToTree(current);
        BitcodeManifestValidator.validate(current, currentRaw, 10, 1_000);

        ObjectNode missing = currentRaw.deepCopy();
        ((ObjectNode) missing.path("records").get(0)).remove("dialect");
        assertReason(missing, BitcodeReasonCode.MANIFEST_SCHEMA_INVALID);

        ObjectNode legacyNull = legacy(currentRaw);
        ((ObjectNode) legacyNull.path("records").get(0)).putNull("dialect");
        assertReason(legacyNull, BitcodeReasonCode.MANIFEST_SCHEMA_INVALID);

        ObjectNode unknown = currentRaw.deepCopy();
        unknown.put("schema_version", "9.9");
        assertReason(unknown, BitcodeReasonCode.MANIFEST_SCHEMA_UNSUPPORTED);

        ObjectNode recordTamper = legacy(currentRaw);
        ((ObjectNode) recordTamper.path("records").get(0).path("source")).put("path", "src/changed.c");
        assertReason(recordTamper, BitcodeReasonCode.MANIFEST_IDENTITY_MISMATCH);

        ObjectNode scopeTamper = legacy(currentRaw);
        ((ObjectNode) scopeTamper.path("scopes").get(0)).put("evidence", "tampered");
        assertReason(scopeTamper, BitcodeReasonCode.MANIFEST_IDENTITY_MISMATCH);

        ObjectNode manifestTamper = legacy(currentRaw);
        manifestTamper.put("status", "FAILED");
        assertReason(manifestTamper, BitcodeReasonCode.MANIFEST_IDENTITY_MISMATCH);
    }

    @Test
    void legacyBundleUsesOriginalRecordDocumentsAndDetectsMemberDamage() throws Exception {
        byte[] content = "valid bundle".getBytes(StandardCharsets.UTF_8);
        ObjectNode raw = legacy(mapper.valueToTree(manifestFor(content)));
        BitcodeManifest manifest = mapper.treeToValue(raw, BitcodeManifest.class);
        Path manifestFile = tempDir.resolve("manifest.json");
        mapper.writeValue(manifestFile.toFile(), raw);
        Path valid = tempDir.resolve("valid.tgz");
        Files.write(valid, bundle(raw, content));

        BitcodeBundleValidator.validate(manifest, raw, manifestFile, valid, mapper, 10, 1_000_000, 1_000_000);

        Path damaged = tempDir.resolve("damaged.tgz");
        Files.write(damaged, bundle(raw, "damaged".getBytes(StandardCharsets.UTF_8)));
        assertThatThrownBy(() -> BitcodeBundleValidator.validate(
                manifest, raw, manifestFile, damaged, mapper, 10, 1_000_000, 1_000_000))
                .isInstanceOfSatisfying(BitcodeRuntimeException.class, ex -> {
                    assertThat(ex.reasonCode()).isEqualTo(BitcodeReasonCode.MEMBER_INTEGRITY_MISMATCH);
                    assertThat(ex.failure().stage()).isEqualTo(BitcodeVerificationStage.MEMBER_INTEGRITY);
                });
    }

    @Test
    void rawSchemaRejectsMalformedContainersAndUndeclaredFieldsAtEveryLevel() throws Exception {
        assertThatThrownBy(() -> BitcodeManifestSchema.validateRaw(null))
                .isInstanceOfSatisfying(BitcodeRuntimeException.class, ex -> {
                    assertThat(ex.reasonCode()).isEqualTo(BitcodeReasonCode.MANIFEST_PARSE_INVALID);
                    assertThat(ex.failure().stage()).isEqualTo(BitcodeVerificationStage.MANIFEST_PARSE);
                });
        assertThatThrownBy(() -> BitcodeManifestSchema.validateRaw(mapper.createArrayNode()))
                .isInstanceOfSatisfying(BitcodeRuntimeException.class,
                        ex -> assertThat(ex.reasonCode()).isEqualTo(BitcodeReasonCode.MANIFEST_PARSE_INVALID));

        ObjectNode current = mapper.valueToTree(manifestFor("valid bundle".getBytes(StandardCharsets.UTF_8)));
        ObjectNode unknownTop = current.deepCopy();
        unknownTop.put("future_field", true);
        assertRawReason(unknownTop, BitcodeReasonCode.MANIFEST_SCHEMA_INVALID);

        ObjectNode missingContainers = current.deepCopy();
        missingContainers.remove("records");
        assertRawReason(missingContainers, BitcodeReasonCode.MANIFEST_SCHEMA_INVALID);

        ObjectNode missingScopes = current.deepCopy();
        missingScopes.remove("scopes");
        assertRawReason(missingScopes, BitcodeReasonCode.MANIFEST_SCHEMA_INVALID);

        ObjectNode objectRecords = current.deepCopy();
        objectRecords.set("records", mapper.createObjectNode());
        assertRawReason(objectRecords, BitcodeReasonCode.MANIFEST_SCHEMA_INVALID);

        ObjectNode objectScopes = current.deepCopy();
        objectScopes.set("scopes", mapper.createObjectNode());
        assertRawReason(objectScopes, BitcodeReasonCode.MANIFEST_SCHEMA_INVALID);

        ObjectNode scalarRecord = current.deepCopy();
        scalarRecord.withArray("records").removeAll().add(1);
        assertRawReason(scalarRecord, BitcodeReasonCode.MANIFEST_SCHEMA_INVALID);

        ObjectNode unknownRecord = current.deepCopy();
        ((ObjectNode) unknownRecord.path("records").get(0)).put("future_record_field", true);
        assertRawReason(unknownRecord, BitcodeReasonCode.MANIFEST_SCHEMA_INVALID);

        ObjectNode scalarScope = current.deepCopy();
        scalarScope.withArray("scopes").removeAll().add(1);
        assertRawReason(scalarScope, BitcodeReasonCode.MANIFEST_SCHEMA_INVALID);

        ObjectNode unknownScope = current.deepCopy();
        ((ObjectNode) unknownScope.path("scopes").get(0)).put("future_scope_field", true);
        assertRawReason(unknownScope, BitcodeReasonCode.MANIFEST_SCHEMA_INVALID);
    }

    @Test
    void verificationFailureSummaryShortensDigestsAndRedactsPathsSecretsAndLongText() {
        BitcodeVerificationFailure failure = new BitcodeVerificationFailure(
                BitcodeVerificationStage.MEMBER_INTEGRITY,
                BitcodeReasonCode.MEMBER_INTEGRITY_MISMATCH,
                "2.0", "producer-1", "a".repeat(64), "b".repeat(64), " ", false,
                "failed at /srv/private/manifest.json token_key=visible\n" + "x".repeat(600),
                "failed at C:\\private\\manifest.json", null, "retry after review");

        var summary = failure.safeSummary();

        assertThat(summary.get("artifactIdentity")).isEqualTo("a".repeat(12));
        assertThat(summary.get("expectedDigest")).isEqualTo("b".repeat(12));
        assertThat(summary.get("actualDigest")).isNull();
        assertThat(summary.get("message").toString()).contains("<PATH>", "<REDACTED>")
                .doesNotContain("/srv/private").hasSize(512);
        assertThat(summary.get("messageEn").toString()).contains("<PATH>")
                .doesNotContain("C:\\private");
        assertThat(summary.get("suggestion")).isNull();

        BitcodeVerificationFailure nonDigest = new BitcodeVerificationFailure(
                BitcodeVerificationStage.MANIFEST_SCHEMA,
                BitcodeReasonCode.MANIFEST_SCHEMA_INVALID,
                null, null, "artifact-alias", null, null, true,
                null, null, null, null);
        assertThat(nonDigest.safeSummary().get("artifactIdentity")).isEqualTo("artifact-alias");
    }

    @Test
    void bundleValidationPreservesSafeSchemaFailureWhenTypedManifestIsAbsent() throws Exception {
        ObjectNode raw = mapper.valueToTree(manifestFor("valid bundle".getBytes(StandardCharsets.UTF_8)));

        assertThatThrownBy(() -> BitcodeBundleValidator.validate(
                null, raw, tempDir.resolve("manifest.json"), tempDir.resolve("bundle.tgz"),
                mapper, 10, 1_000_000, 1_000_000))
                .isInstanceOfSatisfying(BitcodeRuntimeException.class, ex -> {
                    assertThat(ex.reasonCode()).isEqualTo(BitcodeReasonCode.MANIFEST_SCHEMA_INVALID);
                    assertThat(ex.failure().schemaVersion()).isNull();
                    assertThat(ex.failure().producerVersion()).isNull();
                    assertThat(ex.failure().artifactIdentity()).isNull();
                });
    }

    private BitcodeManifest manifestFor(byte[] content) throws Exception {
        String hash = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(content));
        return BitcodeTestFixtures.manifest(List.of(
                BitcodeTestFixtures.produced("compat", "src/compat.c", content.length, hash)));
    }

    private ObjectNode legacy(JsonNode current) {
        ObjectNode raw = current.deepCopy();
        raw.put("schema_version", BitcodeManifest.LEGACY_SCHEMA_VERSION);
        for (JsonNode value : raw.withArray("records")) {
            ObjectNode record = (ObjectNode) value;
            record.remove(List.of("dialect", "standard_source", "standard_option"));
            record.put("semantic_digest", BitcodeCanonicalIdentity.digest(
                    record, "semantic_digest", "artifact_key", "diagnostic"));
        }
        raw.put("semantic_digest", BitcodeCanonicalIdentity.digest(
                raw, "semantic_digest", "generated_at", "artifact_set_id",
                "raw_compile_commands_sha256"));
        raw.put("artifact_set_id", BitcodeCanonicalIdentity.digest(
                raw, "artifact_set_id", "semantic_digest", "generated_at", "diagnostic",
                "raw_compile_commands_sha256"));
        return raw;
    }

    private void assertReason(JsonNode raw, BitcodeReasonCode reason) {
        assertThatThrownBy(() -> {
            BitcodeManifest manifest = mapper.treeToValue(raw, BitcodeManifest.class);
            BitcodeManifestValidator.validate(manifest, raw, 10, 1_000_000);
        }).isInstanceOfSatisfying(BitcodeRuntimeException.class,
                ex -> assertThat(ex.reasonCode()).isEqualTo(reason));
    }

    private void assertRawReason(JsonNode raw, BitcodeReasonCode reason) {
        assertThatThrownBy(() -> BitcodeManifestSchema.validateRaw(raw))
                .isInstanceOfSatisfying(BitcodeRuntimeException.class,
                        ex -> assertThat(ex.reasonCode()).isEqualTo(reason));
    }

    private byte[] bundle(JsonNode raw, byte[] bitcode) throws Exception {
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        try (GzipCompressorOutputStream gzip = new GzipCompressorOutputStream(output);
             TarArchiveOutputStream tar = new TarArchiveOutputStream(gzip)) {
            add(tar, "manifest.json", mapper.writeValueAsBytes(raw));
            JsonNode record = raw.path("records").get(0);
            add(tar, "records/" + record.path("record_id").asText() + ".json",
                    mapper.writeValueAsBytes(record));
            JsonNode scope = raw.path("scopes").get(0);
            add(tar, "scopes/" + scope.path("scope_id").asText() + ".json",
                    mapper.writeValueAsBytes(scope));
            add(tar, record.path("bitcode").path("path").asText(), bitcode);
            tar.finish();
        }
        return output.toByteArray();
    }

    private void add(TarArchiveOutputStream tar, String name, byte[] content) throws Exception {
        TarArchiveEntry entry = new TarArchiveEntry(name);
        entry.setSize(content.length);
        tar.putArchiveEntry(entry);
        tar.write(content);
        tar.closeArchiveEntry();
    }
}
