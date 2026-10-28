package cn.rvport.backend.analysis;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class MemoryOrderResultPolicyTests {
    private final ObjectMapper mapper = new ObjectMapper();

    @Test
    void legacyFindingResponseIsReadOnlyAndNormalizesUnprovenSeverity() {
        for (String verdict : List.of("source-candidate", "risk")) {
            var detail = Map.<String, Object>of("conclusion", Map.of("verdict", verdict, "severity", "medium", "confidence", 0.5));
            var raw = new SpecializedAnalysisFindingView(java.util.UUID.randomUUID(), java.util.UUID.randomUUID(),
                    java.util.UUID.randomUUID(), java.util.UUID.randomUUID(), SpecializedAnalyzerType.MEMORY_ORDER,
                    "id", "FINDING", "MO", "ordering", "MEDIUM", "0.5", "partial", "title", "title-en",
                    "message", "message-en", "suggestion", "suggestion-en", null, null, "a.c", 1, 1, 1, 2,
                    false, "digest", detail, java.time.OffsetDateTime.now());
            var response = SpecializedFindingResponse.from(raw, null);
            assertThat(response.detail()).isSameAs(detail);
            assertThat(raw.confidence()).isEqualTo("0.5");
            assertThat(response.findingKind()).isEqualTo(verdict.equals("risk") ? "FINDING" : "SOURCE_CANDIDATE");
            assertThat(response.confidence()).isEqualTo(verdict.equals("risk") ? "0.5" : null);
            assertThat(response.severity()).isEqualTo(verdict.equals("risk") ? "MEDIUM" : "INFO");
            assertThat(response.requiresHumanConfirmation()).isEqualTo(!verdict.equals("risk"));
        }
    }

    @Test
    void runResponseDoesNotInventZeroDiagnosticsForHistory() {
        var id = java.util.UUID.randomUUID();
        var now = java.time.OffsetDateTime.now();
        for (boolean aggregated : List.of(false, true)) {
            var summary = Map.<String, Object>of("diagnosticCount", 0, "diagnosticsAggregated", aggregated);
            var run = new SpecializedAnalysisRunView(id, id, id, SpecializedAnalyzerType.MEMORY_ORDER,
                    id, id, null, 1L, "tool", "request", "2.0", "policy", SpecializedAnalysisStatus.PARTIAL,
                    "inconclusive", 2, summary, null, null, null, null, 0, 0, 0, id, now, now, now, now);
            assertThat(SpecializedAnalysisResponse.from(run, id).diagnosticCount()).isEqualTo(aggregated ? 0 : null);
            assertThat(run.summary()).isEqualTo(summary);
        }
    }

    @Test
    void kindTakesPrecedenceOverLegacySeverityAndPreservesFormalVerdicts() throws Exception {
        for (var entry : Map.of("risk", "FINDING", "source-candidate", "SOURCE_CANDIDATE",
                "inconclusive", "INCONCLUSIVE", "discharged-within-bounded-model", "DISCHARGED", "unknown", "INCONCLUSIVE").entrySet()) {
            ObjectNode value = mapper.createObjectNode();
            value.putObject("conclusion").put("verdict", entry.getKey()).put("severity", "medium").put("confidence", 0.5);
            assertThat(MemoryOrderResultPolicy.kind("FINDING", value)).isEqualTo(entry.getValue());
            assertThat(MemoryOrderResultPolicy.kind("FINDING", Map.of("conclusion", Map.of("verdict", entry.getKey())))).isEqualTo(entry.getValue());
            assertThat(MemoryOrderResultPolicy.pending(entry.getValue())).isEqualTo(!entry.getKey().equals("risk"));
        }
        assertThat(MemoryOrderResultPolicy.kind("SOURCE_CANDIDATE", Map.of())).isEqualTo("SOURCE_CANDIDATE");
        assertThat(MemoryOrderResultPolicy.kind("FINDING", Map.of("fact", Map.of("kind", "source-candidate"),
                "conclusion", Map.of("verdict", "risk")))).isEqualTo("SOURCE_CANDIDATE");
        assertThat(MemoryOrderResultPolicy.kind(null, Map.of())).isEqualTo("INCONCLUSIVE");
    }

    @Test
    void acceptsExplicitSupportedVersionsAndRejectsUnknownOrMixedVersions() {
        for (String version : List.of("2.0", "3.0")) {
            ObjectNode report = mapper.createObjectNode().put("finding_schema_version", version);
            report.putArray("findings").addObject().put("schemaVersion", version);
            MemoryOrderResultPolicy.validateVersion(report);
            report.withArray("findings").addObject().put("schemaVersion", "future");
            assertThatThrownBy(() -> MemoryOrderResultPolicy.validateVersion(report)).hasMessageContaining("不一致");
        }
        assertThatThrownBy(() -> MemoryOrderResultPolicy.validateVersion(mapper.createObjectNode())).hasMessageContaining("不支持");
    }

    @Test
    void frontierIsVisibleDeduplicatedAndBoundedWithoutMutatingRawData() {
        ObjectNode report = mapper.createObjectNode();
        ObjectNode root = mapper.createObjectNode().put("scope_id", "a").put("code", "facts_partial").put("detail", "事实不完整");
        root.putArray("references").add("tu").add("stage:ingest");
        report.putArray("diagnostics").add(root);
        report.putArray("frontier").add(root.deepCopy().put("stage", "downstream")).add(root.deepCopy().put("scope_id", "b"));
        var summary = MemoryOrderResultPolicy.diagnostics(report);
        assertThat(summary).containsEntry("diagnosticCount", 2).containsEntry("frontierCount", 2)
                .containsEntry("diagnosticsAggregated", true).containsEntry("diagnosticsTruncated", false);
        assertThat(summary.get("primaryDiagnostic").toString()).contains("facts_partial");
        assertThat(summary.get("primaryDiagnostic").toString()).contains("stage:downstream");
        assertThat(root.path("references").toString()).doesNotContain("downstream");
        for (int i = 0; i < 101; i++) report.withArray("frontier").addObject().put("code", "code-" + i);
        summary = MemoryOrderResultPolicy.diagnostics(report);
        assertThat(summary).containsEntry("diagnosticCount", 103).containsEntry("diagnosticsTruncated", true);
        assertThat((List<?>) summary.get("diagnostics")).hasSize(100);
        assertThat(report.withArray("diagnostics")).hasSize(1);
        assertThat(MemoryOrderResultPolicy.diagnostics(mapper.createObjectNode()).get("primaryDiagnostic")).isNull();
        report.putObject("summary").put("diagnostics_total", 120).put("frontier_total", 140);
        assertThat(MemoryOrderResultPolicy.diagnostics(report)).containsEntry("diagnosticCount", 120)
                .containsEntry("frontierCount", 140).containsEntry("diagnosticsTruncated", true);
        ObjectNode truncated = mapper.createObjectNode();
        truncated.putArray("diagnostics").addObject().put("code", "diagnostic-budget-exhausted").putNull("stage");
        assertThat(MemoryOrderResultPolicy.diagnostics(truncated)).containsEntry("diagnosticsTruncated", true);
        assertThat(MemoryOrderResultPolicy.diagnostics(truncated).get("diagnostics").toString()).doesNotContain("stage:null");
    }

    @Test
    void historicalMissingAggregationIsUnknownAndOriginalSummaryIsImmutable() {
        Map<String, Object> original = Map.of("diagnosticCount", 0);
        assertThat(MemoryOrderResultPolicy.historicalSummary(original)).containsEntry("diagnosticCount", null)
                .containsEntry("diagnosticsAggregated", false);
        assertThat(original).containsEntry("diagnosticCount", 0);
        Map<String, Object> current = Map.of("diagnosticCount", 2, "diagnosticsAggregated", true);
        assertThat(MemoryOrderResultPolicy.historicalSummary(current)).isEqualTo(current);
    }
}
