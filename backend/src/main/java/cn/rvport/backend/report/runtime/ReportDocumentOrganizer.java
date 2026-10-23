package cn.rvport.backend.report.runtime;

import cn.rvport.backend.report.ReportInputProjection;
import cn.rvport.backend.report.ReportRepository;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.TreeMap;
import java.util.function.Function;
import java.util.stream.Collectors;

final class ReportDocumentOrganizer {

    private static final List<String> RISK_ORDER = List.of("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO", "COMMENT");

    private ReportDocumentOrganizer() {
    }

    static Map<String, Object> organize(List<ReportRepository.ReportInputSnapshot> snapshots) {
        List<ReportRepository.ReportInputSnapshot> code = snapshots.stream()
                .filter(item -> item.projection() != null && isCodeFinding(item.projection().sourceType()))
                .toList();
        List<ReportRepository.ReportInputSnapshot> dependencies = snapshots.stream()
                .filter(item -> item.projection() != null && "DEPENDENCY_RESULT".equals(item.projection().sourceType()))
                .toList();
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("codeModules", modules(code));
        result.put("dependencyPackages", dependencies(dependencies));
        result.put("rawEvidenceCount", snapshots.size());
        return result;
    }

    private static boolean isCodeFinding(String sourceType) {
        return "KB_FINDING".equals(sourceType)
                || "FLOATING_POINT_FINDING".equals(sourceType)
                || "MEMORY_ORDER_FINDING".equals(sourceType);
    }

    private static List<Map<String, Object>> modules(List<ReportRepository.ReportInputSnapshot> inputs) {
        Map<String, List<ReportRepository.ReportInputSnapshot>> grouped = inputs.stream()
                .collect(Collectors.groupingBy(item -> defaultText(item.projection().moduleKey(), "unlocated"), TreeMap::new, Collectors.toList()));
        List<Map<String, Object>> modules = new ArrayList<>();
        grouped.forEach((moduleKey, moduleInputs) -> {
            ReportInputProjection first = moduleInputs.getFirst().projection();
            Map<String, List<ReportRepository.ReportInputSnapshot>> byFile = moduleInputs.stream()
                    .collect(Collectors.groupingBy(item -> defaultText(item.projection().fileKey(), "unlocated"), TreeMap::new, Collectors.toList()));
            List<Map<String, Object>> files = byFile.entrySet().stream()
                    .map(entry -> file(entry.getKey(), entry.getValue()))
                    .sorted(Comparator.comparing(value -> defaultText(value.get("relativePath"), ""), String.CASE_INSENSITIVE_ORDER))
                    .toList();
            Map<String, Object> module = new LinkedHashMap<>();
            module.put("moduleKey", moduleKey);
            module.put("moduleName", first.moduleName());
            module.put("basis", first.moduleBasis());
            module.put("confidence", first.moduleConfidence());
            module.put("relatedModuleKeys", first.relatedModuleKeys());
            module.put("fileCount", files.size());
            module.put("findingCount", moduleInputs.size());
            module.put("findingTypeCount", distinctCount(moduleInputs, item -> item.projection().findingType()));
            module.put("highestRisk", highestRisk(moduleInputs));
            module.put("riskCounts", counts(moduleInputs, item -> item.projection().riskLevel()));
            module.put("typeCounts", counts(moduleInputs, item -> item.projection().findingType()));
            module.put("files", files);
            modules.add(module);
        });
        modules.sort(Comparator.comparing(value -> defaultText(value.get("moduleName"), ""), String.CASE_INSENSITIVE_ORDER));
        return List.copyOf(modules);
    }

    private static Map<String, Object> file(String fileKey, List<ReportRepository.ReportInputSnapshot> inputs) {
        ReportInputProjection first = inputs.getFirst().projection();
        Map<String, List<ReportRepository.ReportInputSnapshot>> byType = inputs.stream()
                .collect(Collectors.groupingBy(item -> defaultText(item.projection().findingType(), "UNCLASSIFIED"), TreeMap::new, Collectors.toList()));
        List<Map<String, Object>> types = byType.entrySet().stream().map(entry -> type(entry.getKey(), entry.getValue())).toList();
        Map<String, Object> file = new LinkedHashMap<>();
        file.put("fileKey", fileKey);
        file.put("relativePath", first.relativePath());
        file.put("sourceContentHash", first.sourceContentHash());
        file.put("contextAvailable", first.sourceContentHash() != null);
        file.put("findingCount", inputs.size());
        file.put("findingTypeCount", types.size());
        file.put("highestRisk", highestRisk(inputs));
        file.put("riskCounts", counts(inputs, item -> item.projection().riskLevel()));
        file.put("typeCounts", counts(inputs, item -> item.projection().findingType()));
        file.put("findingTypes", types);
        return file;
    }

    private static Map<String, Object> type(String findingType, List<ReportRepository.ReportInputSnapshot> inputs) {
        List<Map<String, Object>> findings = inputs.stream()
                .sorted(findingComparator())
                .map(ReportDocumentOrganizer::finding)
                .toList();
        Map<String, Object> type = new LinkedHashMap<>();
        type.put("findingType", findingType);
        type.put("findingCount", inputs.size());
        type.put("highestRisk", highestRisk(inputs));
        type.put("firstLine", inputs.stream().map(item -> item.projection().lineStart()).filter(Objects::nonNull).min(Integer::compareTo).orElse(null));
        type.put("lastLine", inputs.stream().map(item -> item.projection().lineEnd()).filter(Objects::nonNull).max(Integer::compareTo).orElse(null));
        type.put("symbolCount", distinctCount(inputs, item -> item.projection().symbol()));
        type.put("findings", findings);
        return type;
    }

    private static Map<String, Object> finding(ReportRepository.ReportInputSnapshot input) {
        ReportInputProjection projection = input.projection();
        Map<String, Object> finding = new LinkedHashMap<>();
        finding.put("id", input.ref().id());
        finding.put("sourceRefId", input.ref().sourceRefId());
        finding.put("issueTitle", input.ref().issueTitle());
        finding.put("riskLevel", projection.riskLevel());
        finding.put("findingType", projection.findingType());
        finding.put("lineStart", projection.lineStart());
        finding.put("lineEnd", projection.lineEnd());
        finding.put("columnStart", projection.columnStart());
        finding.put("columnEnd", projection.columnEnd());
        finding.put("symbol", projection.symbol());
        finding.put("locationAvailable", projection.locationAvailable());
        finding.put("recommendation", input.ref().recommendationSummary());
        return finding;
    }

    private static List<Map<String, Object>> dependencies(List<ReportRepository.ReportInputSnapshot> inputs) {
        Map<String, List<ReportRepository.ReportInputSnapshot>> grouped = inputs.stream()
                .collect(Collectors.groupingBy(ReportDocumentOrganizer::dependencyKey, TreeMap::new, Collectors.toList()));
        return grouped.entrySet().stream().map(entry -> {
            List<ReportRepository.ReportInputSnapshot> values = entry.getValue();
            Map<String, Object> first = detail(values.getFirst());
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("packageKey", entry.getKey());
            item.put("packageName", firstNonBlank(first.get("sourceProviderPackage"), first.get("targetProviderPackage"),
                    first.get("sourcePackageName"), first.get("targetPackageName"), first.get("dependencyName"), entry.getKey()));
            item.put("sourceVersion", firstNonBlank(first.get("sourceProviderVersion"), first.get("sourcePackageVersion"),
                    first.get("sourceDetectedVersion"), first.get("dependencyVersion")));
            item.put("targetVersion", firstNonBlank(first.get("targetProviderVersion"), first.get("targetPackageVersion"),
                    first.get("targetDetectedVersion"), first.get("targetVersion")));
            item.put("highestRisk", highestRisk(values));
            item.put("riskCounts", counts(values, value -> value.projection().riskLevel()));
            item.put("dependencyTypes", values.stream().map(value -> detail(value).get("dependencyType")).filter(Objects::nonNull).map(String::valueOf).distinct().sorted().toList());
            item.put("targetMatchStatuses", values.stream().map(value -> detail(value).get("targetMatchStatus")).filter(Objects::nonNull).map(String::valueOf).distinct().sorted().toList());
            item.put("autoFixStatuses", values.stream().map(value -> detail(value).get("autoFixStatus")).filter(Objects::nonNull).map(String::valueOf).distinct().sorted().toList());
            item.put("evidence", values.stream().map(value -> detail(value).get("evidence")).filter(Objects::nonNull).distinct().toList());
            item.put("inputIds", values.stream().map(value -> value.ref().id()).toList());
            return item;
        }).toList();
    }

    private static String dependencyKey(ReportRepository.ReportInputSnapshot input) {
        Map<String, Object> detail = detail(input);
        return defaultText(firstNonBlank(detail.get("sourceProviderPackage"), detail.get("targetProviderPackage"),
                detail.get("sourcePackageName"), detail.get("targetPackageName"), detail.get("dependencyName"),
                input.ref().identityPath()), "unknown").toLowerCase(Locale.ROOT);
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> detail(ReportRepository.ReportInputSnapshot input) {
        Object value = input.snapshot().get("sourceDetail");
        if (!(value instanceof Map<?, ?> map)) {
            return Map.of();
        }
        Map<String, Object> result = new LinkedHashMap<>();
        map.forEach((key, item) -> result.put(String.valueOf(key), item));
        return result;
    }

    private static Comparator<ReportRepository.ReportInputSnapshot> findingComparator() {
        return Comparator.comparing((ReportRepository.ReportInputSnapshot item) -> item.projection().lineStart(), Comparator.nullsLast(Integer::compareTo))
                .thenComparing(item -> item.projection().lineEnd(), Comparator.nullsLast(Integer::compareTo))
                .thenComparing(item -> item.ref().id());
    }

    private static Map<String, Long> counts(List<ReportRepository.ReportInputSnapshot> inputs, Function<ReportRepository.ReportInputSnapshot, String> classifier) {
        return inputs.stream().map(classifier).map(value -> defaultText(value, "UNKNOWN"))
                .collect(Collectors.groupingBy(Function.identity(), LinkedHashMap::new, Collectors.counting()));
    }

    private static long distinctCount(List<ReportRepository.ReportInputSnapshot> inputs, Function<ReportRepository.ReportInputSnapshot, String> classifier) {
        return inputs.stream().map(classifier).filter(value -> value != null && !value.isBlank()).distinct().count();
    }

    private static String highestRisk(List<ReportRepository.ReportInputSnapshot> inputs) {
        return inputs.stream().map(item -> defaultText(item.projection().riskLevel(), "INFO"))
                .min(Comparator.comparingInt(ReportDocumentOrganizer::riskRank)).orElse("INFO");
    }

    private static int riskRank(String value) {
        int index = RISK_ORDER.indexOf(defaultText(value, "INFO").toUpperCase(Locale.ROOT));
        return index < 0 ? RISK_ORDER.indexOf("INFO") : index;
    }

    private static String firstNonBlank(Object... values) {
        for (Object value : values) {
            if (value != null && !String.valueOf(value).isBlank()) {
                return String.valueOf(value).trim();
            }
        }
        return null;
    }

    private static String defaultText(Object value, String fallback) {
        return value == null || String.valueOf(value).isBlank() ? fallback : String.valueOf(value);
    }
}
