package cn.rvport.backend.analysis;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeSet;

/** 内存序结果的只读消费策略；原始证据与用户纳入选择保持独立。 */
public final class MemoryOrderResultPolicy {
    private MemoryOrderResultPolicy() {}

    public static String kind(String declared, JsonNode value) {
        return classify(declared, value.path("conclusion").path("verdict").asText(), value.path("fact").path("kind").asText());
    }

    public static String kind(String declared, Map<String, Object> value) {
        Object conclusion = value.get("conclusion"), fact = value.get("fact");
        return classify(declared, conclusion instanceof Map<?, ?> map ? String.valueOf(map.get("verdict")) : "",
                fact instanceof Map<?, ?> map ? String.valueOf(map.get("kind")) : "");
    }

    private static String classify(String declared, String verdict, String factKind) {
        if ("SOURCE_CANDIDATE".equals(declared) || "source-candidate".equals(verdict)
                || "source-candidate".equals(factKind)) return "SOURCE_CANDIDATE";
        if ("inconclusive".equals(verdict)) return "INCONCLUSIVE";
        if ("discharged-within-bounded-model".equals(verdict)) return "DISCHARGED";
        return "risk".equals(verdict) ? "FINDING" : "INCONCLUSIVE";
    }

    public static boolean pending(String kind) {
        return !"FINDING".equals(kind);
    }

    public static void validateVersion(JsonNode report) {
        String version = report.path("finding_schema_version").asText();
        if (!List.of("2.0", "3.0").contains(version)) {
            throw new SpecializedAnalysisRuntimeException("不支持的内存序 Finding 协议版本：" + version);
        }
        for (String collection : List.of("findings", "source_candidates", "discharged_assessments")) {
            for (JsonNode value : report.path(collection)) {
                if (!version.equals(value.path("schemaVersion").asText())) {
                    throw new SpecializedAnalysisRuntimeException("内存序 Finding 与报告协议版本不一致");
                }
            }
        }
    }

    public static Map<String, Object> diagnostics(JsonNode report) {
        Map<String, JsonNode> unique = new LinkedHashMap<>();
        for (String collection : List.of("diagnostics", "frontier")) {
            for (JsonNode item : report.path(collection)) {
                List<String> refs = new ArrayList<>();
                item.path("references").forEach(ref -> { if (!ref.asText().startsWith("stage:")) refs.add(ref.asText()); });
                refs.sort(String::compareTo);
                String key = List.of(item.path("scope_id").asText(), item.path("code").asText(),
                        refs.toString(), item.path("detail").asText(), item.path("detail_en").asText()).toString();
                JsonNode retained = unique.computeIfAbsent(key, ignored -> item.deepCopy());
                if (retained instanceof ObjectNode object) {
                    var combined = new TreeSet<String>();
                    retained.path("references").forEach(ref -> combined.add(ref.asText()));
                    item.path("references").forEach(ref -> combined.add(ref.asText()));
                    if (!item.path("stage").asText("").isEmpty()) combined.add("stage:" + item.path("stage").asText());
                    var array = object.putArray("references");
                    combined.forEach(array::add);
                }
            }
        }
        List<Map<String, Object>> details = unique.values().stream().limit(100).map(item -> {
            Map<String, Object> detail = new LinkedHashMap<>();
            for (String name : List.of("code", "stage", "scope_id", "detail", "detail_en", "suggestion", "suggestion_en")) {
                detail.put(name, item.path(name).asText(""));
            }
            detail.put("references", item.path("references"));
            return detail;
        }).toList();
        Map<String, Object> result = new LinkedHashMap<>();
        int total = Math.max(unique.size(), report.path("summary").path("diagnostics_total").asInt());
        result.put("diagnosticCount", total);
        result.put("frontierCount", Math.max(report.path("frontier").size(), report.path("summary").path("frontier_total").asInt()));
        result.put("diagnostics", details);
        result.put("primaryDiagnostic", details.isEmpty() ? null : details.getFirst());
        result.put("diagnosticsTruncated", total > details.size() || unique.values().stream()
                .anyMatch(item -> "diagnostic-budget-exhausted".equals(item.path("code").asText())));
        result.put("diagnosticsAggregated", true);
        result.put("diagnosticsDownload", "result-json");
        return result;
    }

    public static Map<String, Object> historicalSummary(Map<String, Object> original) {
        Map<String, Object> result = new LinkedHashMap<>(original);
        if (!Boolean.TRUE.equals(original.get("diagnosticsAggregated"))) {
            result.put("diagnosticCount", null);
            result.put("diagnosticsAggregated", false);
            result.put("diagnosticsMessage", "历史结果的诊断未完整汇总，请查看原始结果");
            result.put("diagnosticsMessageEn", "Diagnostics were not fully aggregated for this historical result; inspect the original report");
        }
        return result;
    }
}
