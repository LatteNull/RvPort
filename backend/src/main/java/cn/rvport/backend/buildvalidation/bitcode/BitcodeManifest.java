package cn.rvport.backend.buildvalidation.bitcode;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;
import java.util.Map;

/** 平台级共享 LLVM BC 制品合同。该模型不得包含 RvPort 业务主键或真实绝对路径。 */
public record BitcodeManifest(
        String kind,
        @JsonProperty("schema_version") String schemaVersion,
        @JsonProperty("artifact_set_id") String artifactSetId,
        @JsonProperty("source_identity_digest") String sourceIdentityDigest,
        @JsonProperty("compile_context") CompileContext compileContext,
        Producer producer,
        String status,
        Counts counts,
        List<ArtifactRecord> records,
        List<Scope> scopes,
        @JsonProperty("generated_at") Instant generatedAt,
        @JsonProperty("semantic_digest") String semanticDigest
) {
    public static final String KIND = "SharedLlvmBitcodeArtifactSet";
    public static final String SCHEMA_VERSION = "2.1";
    public static final String LEGACY_SCHEMA_VERSION = "2.0";

    public record CompileContext(
            @JsonProperty("raw_compile_commands_sha256") String rawCompileCommandsSha256,
            @JsonProperty("normalized_digest") String normalizedDigest
    ) {
    }

    public record Producer(String family, String version,
                           @JsonProperty("llvm_version") String llvmVersion,
                           @JsonProperty("host_triple") String hostTriple) {
    }

    public record Counts(@JsonProperty("planned_contexts") int plannedContexts,
                         @JsonProperty("planned_records") int plannedRecords,
                         int produced, int missing, int failed,
                         @JsonProperty("total_bytes") long totalBytes) {
    }

    public record ArtifactRecord(
            @JsonProperty("record_id") String recordId,
            @JsonProperty("physical_tu_id") String physicalTuId,
            @JsonProperty("context_id") String contextId,
            @JsonProperty("artifact_key") String artifactKey,
            Profile profile,
            String status,
            Diagnostic diagnostic,
            Bitcode bitcode,
            @JsonProperty("production_compiler") Compiler productionCompiler,
            Producer producer,
            Target target,
            String language,
            String standard,
            String dialect,
            @JsonProperty("standard_source") String standardSource,
            @JsonProperty("standard_option") String standardOption,
            String optimization,
            String debug,
            @JsonProperty("module_kind") String moduleKind,
            Source source,
            @JsonProperty("compile_record_digest") String compileRecordDigest,
            @JsonProperty("input_digests") Map<String, String> inputDigests,
            Provenance provenance,
            List<String> capabilities,
            List<Sidecar> sidecars,
            @JsonProperty("semantic_digest") String semanticDigest
    ) {
        public ArtifactRecord(
                String recordId, String physicalTuId, String contextId, String artifactKey,
                Profile profile, String status, Diagnostic diagnostic, Bitcode bitcode,
                Compiler productionCompiler, Producer producer, Target target, String language,
                String standard, String optimization, String debug, String moduleKind, Source source,
                String compileRecordDigest, Map<String, String> inputDigests, Provenance provenance,
                List<String> capabilities, List<Sidecar> sidecars, String semanticDigest
        ) {
            this(recordId, physicalTuId, contextId, artifactKey, profile, status, diagnostic, bitcode,
                    productionCompiler, producer, target, language, standard, null, null, null,
                    optimization, debug, moduleKind, source, compileRecordDigest, inputDigests,
                    provenance, capabilities, sidecars, semanticDigest);
        }
    }

    public record Profile(String name, String version) {
    }

    public record Diagnostic(String code, String detail,
                             @JsonProperty("detail_en") String detailEn,
                             String suggestion,
                             @JsonProperty("suggestion_en") String suggestionEn) {
    }

    public record Bitcode(String path, long bytes, String sha256) {
    }

    public record Compiler(String family, String executable, String version) {
    }

    public record Target(String triple, @JsonProperty("data_layout") String dataLayout,
                         Map<String, Object> abi) {
    }

    public record Source(String path, String sha256) {
    }

    public record Provenance(String completeness, List<String> gaps) {
    }

    public record Sidecar(String kind, @JsonProperty("schema_version") String schemaVersion,
                          String path, long bytes, String sha256, List<String> capabilities) {
    }

    public record Scope(@JsonProperty("scope_id") String scopeId,
                        @JsonProperty("target_id") String targetId,
                        @JsonProperty("record_ids") List<String> recordIds,
                        String evidence, boolean closed,
                        @JsonProperty("external_boundaries") List<String> externalBoundaries,
                        @JsonProperty("target_triple") String targetTriple,
                        @JsonProperty("semantic_digest") String semanticDigest) {
    }
}
