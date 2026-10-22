package cn.rvport.backend.buildvalidation.bitcode;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.nio.file.Path;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

public final class BitcodeManifestValidator {

    private static final ObjectMapper MAPPER = new ObjectMapper().findAndRegisterModules();

    private static final Set<String> STATUSES = Set.of("produced", "missing", "failed");
    private static final Set<String> PROFILES = Set.of("source-preserving", "build-faithful");
    private static final Set<String> SOURCE_CAPABILITIES = Set.of(
            "llvm.ir-readable", "debug.locations", "source.correlation", "fp.operations",
            "fp.fast-math-flags", "memory.atomic-ordering", "memory.syncscope", "memory.fence",
            "target.triple", "target.data-layout", "symbols.linkage");

    private BitcodeManifestValidator() {
    }

    public static void validate(BitcodeManifest manifest, int maxRecords, long maxBundleBytes) {
        validate(manifest, manifest == null ? null : MAPPER.valueToTree(manifest), maxRecords, maxBundleBytes);
    }

    public static void validate(BitcodeManifest manifest, JsonNode rawManifest,
                                int maxRecords, long maxBundleBytes) {
        String schemaVersion = BitcodeManifestSchema.validateRaw(rawManifest);
        if (manifest == null || !BitcodeManifest.KIND.equals(manifest.kind())
                || !(BitcodeManifest.SCHEMA_VERSION.equals(manifest.schemaVersion())
                || BitcodeManifest.LEGACY_SCHEMA_VERSION.equals(manifest.schemaVersion()))) {
            throw new IllegalArgumentException("BC manifest schema 不受支持");
        }
        requireHash(manifest.artifactSetId(), "artifact_set_id");
        requireHash(manifest.sourceIdentityDigest(), "source_identity_digest");
        if (manifest.compileContext() == null) {
            throw new IllegalArgumentException("BC manifest compile_context 缺失");
        }
        requireHash(manifest.compileContext().rawCompileCommandsSha256(), "raw compile database");
        requireHash(manifest.compileContext().normalizedDigest(), "normalized compile context");
        validateProducer(manifest.producer());
        if (manifest.counts() == null || manifest.records() == null || manifest.scopes() == null
                || manifest.records().size() > maxRecords || manifest.scopes().isEmpty()) {
            throw new IllegalArgumentException("BC manifest record/scope 数量非法");
        }
        validateRecords(manifest, rawManifest.path("records"), maxBundleBytes);
        validateScopes(manifest.records(), manifest.scopes(), rawManifest.path("scopes"));
        requireHash(manifest.semanticDigest(), "manifest semantic_digest");
        if (!BitcodeCanonicalIdentity.digest(rawManifest,
                "semantic_digest", "generated_at", "artifact_set_id", "raw_compile_commands_sha256")
                .equals(manifest.semanticDigest())) {
            throw identityFailure(schemaVersion, "BC manifest semantic_digest 不一致");
        }
        if (!BitcodeCanonicalIdentity.digest(rawManifest,
                "artifact_set_id", "semantic_digest", "generated_at", "diagnostic",
                "raw_compile_commands_sha256")
                .equals(manifest.artifactSetId())) {
            throw identityFailure(schemaVersion, "BC manifest artifact_set_id 不一致");
        }
    }

    private static void validateRecords(BitcodeManifest manifest, JsonNode rawRecords,
                                        long maxBundleBytes) {
        Set<String> recordIds = new HashSet<>();
        Set<String> artifactKeys = new HashSet<>();
        Set<String> paths = new HashSet<>();
        long totalBytes = 0;
        int produced = 0;
        int missing = 0;
        int failed = 0;
        for (int index = 0; index < manifest.records().size(); index++) {
            BitcodeManifest.ArtifactRecord record = manifest.records().get(index);
            JsonNode rawRecord = rawRecords.path(index);
            requireHash(record.recordId(), "record_id");
            requireHash(record.physicalTuId(), "physical_tu_id");
            requireHash(record.contextId(), "context_id");
            requireHash(record.artifactKey(), "artifact_key");
            requireHash(record.semanticDigest(), "record semantic_digest");
            if (!recordIds.add(record.recordId())) {
                throw new IllegalArgumentException("BC manifest record_id 重复: " + record.recordId());
            }
            if (!artifactKeys.add(record.artifactKey())) {
                throw new IllegalArgumentException("BC manifest artifact_key 重复: " + record.artifactKey());
            }
            if (!STATUSES.contains(record.status())) {
                throw new IllegalArgumentException("BC manifest record status 非法: " + record.status());
            }
            if (record.profile() == null || !PROFILES.contains(record.profile().name())
                    || blank(record.profile().version())) {
                throw new IllegalArgumentException("BC manifest record profile 非法");
            }
            ObjectNode recordIdentity = MAPPER.createObjectNode();
            recordIdentity.set("context_id", rawRecord.get("context_id"));
            recordIdentity.set("profile", rawRecord.get("profile"));
            if (!BitcodeCanonicalIdentity.digest(recordIdentity).equals(record.recordId())) {
                throw identityFailure(manifest.schemaVersion(), "BC manifest record_id 不一致");
            }
            validateRecordContext(record);
            if (BitcodeManifest.SCHEMA_VERSION.equals(manifest.schemaVersion())) {
                validateLanguageStandard(record);
            }
            if (!BitcodeCanonicalIdentity.digest(rawRecord, "semantic_digest", "artifact_key", "diagnostic")
                    .equals(record.semanticDigest())) {
                throw identityFailure(manifest.schemaVersion(),
                        "BC manifest record semantic_digest 不一致");
            }
            ObjectNode artifactIdentity = MAPPER.createObjectNode();
            artifactIdentity.set("context_id", rawRecord.get("context_id"));
            artifactIdentity.set("profile", rawRecord.get("profile"));
            artifactIdentity.set("producer", rawRecord.get("producer"));
            JsonNode rawBitcode = rawRecord.get("bitcode");
            artifactIdentity.set("bitcode_sha256",
                    rawBitcode == null || rawBitcode.isNull()
                            ? MAPPER.nullNode() : rawBitcode.get("sha256"));
            if (!BitcodeCanonicalIdentity.digest(artifactIdentity).equals(record.artifactKey())) {
                throw new IllegalArgumentException("BC manifest artifact_key 不一致");
            }
            if ("produced".equals(record.status())) {
                produced++;
                if (record.diagnostic() != null || record.bitcode() == null) {
                    throw new IllegalArgumentException("produced record 的 BC/diagnostic 非法");
                }
                validateSafeRelativePath(record.bitcode().path(), "bitcode.path");
                if (!paths.add(record.bitcode().path()) || record.bitcode().bytes() < 4) {
                    throw new IllegalArgumentException("BC manifest bitcode 路径或大小非法");
                }
                requireHash(record.bitcode().sha256(), "bitcode.sha256");
                totalBytes = Math.addExact(totalBytes, record.bitcode().bytes());
            } else {
                if ("missing".equals(record.status())) {
                    missing++;
                } else {
                    failed++;
                }
                if (record.bitcode() != null || record.diagnostic() == null
                        || blank(record.diagnostic().code()) || record.diagnostic().detail() == null
                        || record.diagnostic().detailEn() == null) {
                    throw new IllegalArgumentException("missing/failed record 缺少双语诊断或错误引用 BC");
                }
            }
            for (BitcodeManifest.Sidecar sidecar : record.sidecars()) {
                validateSafeRelativePath(sidecar.path(), "sidecar.path");
                requireHash(sidecar.sha256(), "sidecar.sha256");
                if (!paths.add(sidecar.path()) || sidecar.bytes() < 0 || blank(sidecar.kind())
                        || blank(sidecar.schemaVersion())) {
                    throw new IllegalArgumentException("BC manifest sidecar 非法");
                }
                totalBytes = Math.addExact(totalBytes, sidecar.bytes());
            }
        }
        BitcodeManifest.Counts counts = manifest.counts();
        if (counts.plannedRecords() != manifest.records().size() || counts.plannedContexts() < 0
                || counts.plannedContexts() > counts.plannedRecords() || counts.produced() != produced
                || counts.missing() != missing || counts.failed() != failed
                || counts.totalBytes() != totalBytes || totalBytes > maxBundleBytes) {
            throw new IllegalArgumentException("BC manifest 聚合计数不一致");
        }
    }

    private static void validateLanguageStandard(BitcodeManifest.ArtifactRecord record) {
        Set<String> standards = "compiler-default".equals(record.standard())
                ? Set.of("compiler-default") : "c++".equals(record.language())
                ? Set.of("unsupported", "c++98", "c++03", "c++11", "c++14", "c++17", "c++20", "c++23")
                : Set.of("unsupported", "c89", "c99", "c11", "c17", "c23");
        if (!standards.contains(record.standard())
                || !("iso".equals(record.dialect()) || "gnu".equals(record.dialect())
                || "compiler-default".equals(record.dialect()))
                || !("explicit".equals(record.standardSource())
                || "compiler-default".equals(record.standardSource()))) {
            throw new IllegalArgumentException("BC manifest record 语言标准上下文非法");
        }
        if ("unsupported".equals(record.standard()) && "produced".equals(record.status())) {
            throw new IllegalArgumentException("不支持的语言标准不得生成可信 BC");
        }
        if ("explicit".equals(record.standardSource()) && blank(record.standardOption())) {
            throw new IllegalArgumentException("BC manifest record 缺少原始 -std 参数");
        }
        if ("compiler-default".equals(record.standardSource()) && record.standardOption() != null) {
            throw new IllegalArgumentException("compiler-default 不应携带 -std 参数");
        }
        if ("compiler-default".equals(record.standardSource())
                && (!("compiler-default".equals(record.standard()))
                || !("compiler-default".equals(record.dialect())))) {
            throw new IllegalArgumentException("compiler-default 不应伪造基础标准或方言");
        }
    }

    private static void validateRecordContext(BitcodeManifest.ArtifactRecord record) {
        if (record.source() == null || record.productionCompiler() == null || record.producer() == null
                || record.target() == null || record.inputDigests() == null || record.provenance() == null
                || record.capabilities() == null || record.sidecars() == null || blank(record.language())
                || blank(record.standard()) || blank(record.optimization()) || blank(record.debug())
                || !"translation-unit".equals(record.moduleKind())) {
            throw new IllegalArgumentException("BC manifest record production context 不完整");
        }
        validateSafeRelativePath(record.source().path(), "source.path");
        requireHash(record.source().sha256(), "source.sha256");
        requireHash(record.compileRecordDigest(), "compile_record_digest");
        record.inputDigests().forEach((path, hash) -> {
            validateSafeRelativePath(path, "input_digest.path");
            requireHash(hash, "input_digest.sha256");
        });
        validateProducer(record.producer());
        if (blank(record.target().triple()) || blank(record.target().dataLayout()) || record.target().abi() == null) {
            throw new IllegalArgumentException("BC manifest target 不完整");
        }
        if ("source-preserving".equals(record.profile().name())
                && !record.capabilities().containsAll(SOURCE_CAPABILITIES)) {
            throw new IllegalArgumentException("source-preserving record capability 不完整");
        }
    }

    private static void validateScopes(List<BitcodeManifest.ArtifactRecord> records,
                                       List<BitcodeManifest.Scope> scopes,
                                       JsonNode rawScopes) {
        Set<String> recordIds = records.stream().map(BitcodeManifest.ArtifactRecord::recordId)
                .collect(Collectors.toSet());
        Set<String> scopeIds = new HashSet<>();
        Set<String> scoped = new HashSet<>();
        for (int index = 0; index < scopes.size(); index++) {
            BitcodeManifest.Scope scope = scopes.get(index);
            JsonNode rawScope = rawScopes.path(index);
            requireHash(scope.scopeId(), "scope_id");
            requireHash(scope.targetId(), "target_id");
            requireHash(scope.semanticDigest(), "scope semantic_digest");
            if (!scopeIds.add(scope.scopeId()) || scope.recordIds() == null || scope.recordIds().isEmpty()
                    || new HashSet<>(scope.recordIds()).size() != scope.recordIds().size()
                    || !recordIds.containsAll(scope.recordIds()) || blank(scope.evidence())
                    || blank(scope.targetTriple()) || scope.externalBoundaries() == null) {
                throw new IllegalArgumentException("BC manifest scope 非法");
            }
            scoped.addAll(scope.recordIds());
            if (!BitcodeCanonicalIdentity.digest(rawScope, "semantic_digest", "scope_id")
                    .equals(scope.semanticDigest())) {
                throw identityFailure(null, "BC manifest scope semantic_digest 不一致");
            }
            ObjectNode scopeIdentity = MAPPER.createObjectNode();
            scopeIdentity.set("target_id", rawScope.get("target_id"));
            scopeIdentity.set("record_ids", rawScope.get("record_ids"));
            scopeIdentity.set("closed", rawScope.get("closed"));
            scopeIdentity.set("semantic_digest", rawScope.get("semantic_digest"));
            if (!BitcodeCanonicalIdentity.digest(scopeIdentity).equals(scope.scopeId())) {
                throw identityFailure(null, "BC manifest scope_id 不一致");
            }
        }
        if (!scoped.containsAll(recordIds)) {
            throw new IllegalArgumentException("BC manifest scope 未覆盖完整计划分母");
        }
    }

    private static void validateProducer(BitcodeManifest.Producer producer) {
        if (producer == null || blank(producer.family()) || blank(producer.version())
                || blank(producer.llvmVersion()) || blank(producer.hostTriple())) {
            throw new IllegalArgumentException("BC manifest producer 不完整");
        }
    }

    public static void validateSafeRelativePath(String value, String field) {
        if (blank(value) || value.indexOf('\0') >= 0 || value.indexOf('\\') >= 0) {
            throw new IllegalArgumentException("BC manifest " + field + " 必须是 POSIX 安全相对路径");
        }
        Path path = Path.of(value).normalize();
        if (value.startsWith("/") || value.matches("^[A-Za-z]:/.*") || path.isAbsolute()
                || path.startsWith("..") || !path.toString().replace('\\', '/').equals(value)) {
            throw new IllegalArgumentException("BC manifest " + field + " 必须是 POSIX 安全相对路径");
        }
    }

    private static void requireHash(String value, String field) {
        if (value == null || !value.matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException("BC manifest " + field + " 不是 SHA-256");
        }
    }

    private static boolean blank(String value) {
        return value == null || value.isBlank();
    }

    private static BitcodeRuntimeException identityFailure(String schema, String message) {
        return BitcodeManifestSchema.failure(BitcodeVerificationStage.MANIFEST_IDENTITY,
                BitcodeReasonCode.MANIFEST_IDENTITY_MISMATCH, schema, message,
                "The BC manifest canonical identity does not match its declared digest.");
    }
}
