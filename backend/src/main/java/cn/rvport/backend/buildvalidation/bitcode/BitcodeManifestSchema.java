package cn.rvport.backend.buildvalidation.bitcode;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.Iterator;
import java.util.Map;
import java.util.Set;

/**
 * 在绑定 Java record 前约束 manifest 的原始 schema 表示。
 *
 * <p>身份摘要必须基于 producer 实际发布的字段集合，不能基于当前 Java model
 * 回写出来的 null 字段。</p>
 */
public final class BitcodeManifestSchema {

    private static final Set<String> TOP = Set.of(
            "kind", "schema_version", "artifact_set_id", "source_identity_digest",
            "compile_context", "producer", "status", "counts", "records", "scopes",
            "generated_at", "semantic_digest");
    private static final Set<String> LEGACY_RECORD = Set.of(
            "record_id", "physical_tu_id", "context_id", "artifact_key", "profile", "status",
            "diagnostic", "bitcode", "production_compiler", "producer", "target", "language",
            "standard", "optimization", "debug", "module_kind", "source",
            "compile_record_digest", "input_digests", "provenance", "capabilities", "sidecars",
            "semantic_digest");
    private static final Set<String> CURRENT_RECORD = Set.of(
            "record_id", "physical_tu_id", "context_id", "artifact_key", "profile", "status",
            "diagnostic", "bitcode", "production_compiler", "producer", "target", "language",
            "standard", "dialect", "standard_source", "standard_option", "optimization", "debug",
            "module_kind", "source", "compile_record_digest", "input_digests", "provenance",
            "capabilities", "sidecars", "semantic_digest");
    private static final Set<String> SCOPE = Set.of(
            "scope_id", "target_id", "record_ids", "evidence", "closed",
            "external_boundaries", "target_triple", "semantic_digest");

    private BitcodeManifestSchema() {
    }

    public static String validateRaw(JsonNode root) {
        if (root == null || !root.isObject()) {
            throw failure(BitcodeVerificationStage.MANIFEST_PARSE,
                    BitcodeReasonCode.MANIFEST_PARSE_INVALID,
                    null, "BC manifest 必须是 JSON 对象", "The BC manifest must be a JSON object.");
        }
        rejectUnknown(root, TOP, "manifest");
        String version = text(root, "schema_version");
        if (!(BitcodeManifest.LEGACY_SCHEMA_VERSION.equals(version)
                || BitcodeManifest.SCHEMA_VERSION.equals(version))) {
            throw failure(BitcodeVerificationStage.MANIFEST_SCHEMA,
                    BitcodeReasonCode.MANIFEST_SCHEMA_UNSUPPORTED,
                    version, "BC manifest schema 不受支持", "The BC manifest schema is unsupported.");
        }
        JsonNode records = root.get("records");
        JsonNode scopes = root.get("scopes");
        if (records == null || !records.isArray() || scopes == null || !scopes.isArray()) {
            throw failure(BitcodeVerificationStage.MANIFEST_SCHEMA,
                    BitcodeReasonCode.MANIFEST_SCHEMA_INVALID, version,
                    "BC manifest records/scopes 类型非法",
                    "The BC manifest records/scopes shape is invalid.");
        }
        Set<String> recordFields = BitcodeManifest.LEGACY_SCHEMA_VERSION.equals(version)
                ? LEGACY_RECORD : CURRENT_RECORD;
        for (JsonNode record : records) {
            if (!record.isObject()) {
                throw failure(BitcodeVerificationStage.MANIFEST_SCHEMA,
                        BitcodeReasonCode.MANIFEST_SCHEMA_INVALID, version,
                        "BC manifest record 必须是对象", "Each BC manifest record must be an object.");
            }
            rejectUnknown(record, recordFields, "record");
            if (BitcodeManifest.SCHEMA_VERSION.equals(version)) {
                for (String name : Set.of("dialect", "standard_source", "standard_option")) {
                    if (!record.has(name)) {
                        throw failure(BitcodeVerificationStage.MANIFEST_SCHEMA,
                                BitcodeReasonCode.MANIFEST_SCHEMA_INVALID, version,
                                "BC manifest 2.1 record 缺少语言标准字段",
                                "A BC manifest 2.1 record is missing language-standard fields.");
                    }
                }
            }
        }
        for (JsonNode scope : scopes) {
            if (!scope.isObject()) {
                throw failure(BitcodeVerificationStage.MANIFEST_SCHEMA,
                        BitcodeReasonCode.MANIFEST_SCHEMA_INVALID, version,
                        "BC manifest scope 必须是对象", "Each BC manifest scope must be an object.");
            }
            rejectUnknown(scope, SCOPE, "scope");
        }
        return version;
    }

    private static void rejectUnknown(JsonNode node, Set<String> allowed, String label) {
        Iterator<Map.Entry<String, JsonNode>> fields = node.fields();
        while (fields.hasNext()) {
            String name = fields.next().getKey();
            if (!allowed.contains(name)) {
                throw failure(BitcodeVerificationStage.MANIFEST_SCHEMA,
                        BitcodeReasonCode.MANIFEST_SCHEMA_INVALID,
                        text(node, "schema_version"),
                        "BC manifest " + label + " 包含版本未声明字段",
                        "The BC manifest " + label + " contains a field not declared by its schema.");
            }
        }
    }

    private static String text(JsonNode node, String field) {
        JsonNode value = node == null ? null : node.get(field);
        return value != null && value.isTextual() ? value.textValue() : null;
    }

    static BitcodeRuntimeException failure(BitcodeVerificationStage stage, BitcodeReasonCode reason,
                                           String schema, String message, String messageEn) {
        return new BitcodeRuntimeException(new BitcodeVerificationFailure(
                stage, reason, schema, null, null, null, null, false,
                message, messageEn,
                "检查 manifest/bundle 生产版本与摘要后重新构建制品。",
                "Check the manifest/bundle producer version and digests, then rebuild the artifact."), null);
    }
}
