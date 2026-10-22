package cn.rvport.backend.dependency.autofix;

import cn.rvport.backend.dependency.DependencyAnalysisResultItemView;
import cn.rvport.backend.dependency.DependencyRiskLevel;

import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Set;

public class DependencyAutoFixCandidatePolicy {

    private static final Set<String> ALLOWED_SORTS = Set.of(
            "createdAt",
            "dependencyName",
            "riskLevel",
            "targetMatchStatus",
            "installPackageName",
            "defaultSelected",
            "selectable"
    );

    public DependencyAutoFixCandidateResponse candidate(DependencyAnalysisResultItemView item) {
        if (item.riskLevel() == DependencyRiskLevel.MEDIUM && hasText(item.targetProviderPackage())) {
            return new DependencyAutoFixCandidateResponse(
                    item.id(),
                    item.dependencyType(),
                    item.dependencyName(),
                    item.dependencyVersion(),
                    item.riskLevel(),
                    item.targetMatchStatus(),
                    item.sourceProviderPackage(),
                    item.sourceProviderVersion(),
                    item.targetProviderPackage(),
                    item.targetProviderVersion(),
                    item.targetProviderPackage().trim(),
                    blankToNull(item.targetProviderVersion()),
                    true,
                    true,
                    "目标环境或目标软件源已确认存在可安装包"
            );
        }
        if (item.riskLevel() == DependencyRiskLevel.HIGH && hasText(item.sourceProviderPackage())) {
            return new DependencyAutoFixCandidateResponse(
                    item.id(),
                    item.dependencyType(),
                    item.dependencyName(),
                    item.dependencyVersion(),
                    item.riskLevel(),
                    item.targetMatchStatus(),
                    item.sourceProviderPackage(),
                    item.sourceProviderVersion(),
                    item.targetProviderPackage(),
                    item.targetProviderVersion(),
                    firstNonBlank(item.targetProviderPackage(), item.sourceProviderPackage()),
                    majorVersion(item.sourceProviderVersion()),
                    false,
                    true,
                    "高风险条目仅展示为可选项，将按源侧包名和主版本尝试匹配目标源"
            );
        }
        return new DependencyAutoFixCandidateResponse(
                item.id(),
                item.dependencyType(),
                item.dependencyName(),
                item.dependencyVersion(),
                item.riskLevel(),
                item.targetMatchStatus(),
                item.sourceProviderPackage(),
                item.sourceProviderVersion(),
                item.targetProviderPackage(),
                item.targetProviderVersion(),
                null,
                null,
                false,
                false,
                "该结果缺少可确认安装计划或不属于自动修复风险范围"
        );
    }

    public List<DependencyAutoFixCandidateResponse> filterAndSort(
            List<DependencyAutoFixCandidateResponse> candidates,
            DependencyAutoFixCandidateListRequest request
    ) {
        return candidates.stream()
                .filter(candidate -> !request.effectiveSelectable() || candidate.selectable())
                .filter(candidate -> request.dependencyType() == null || candidate.dependencyType() == request.dependencyType())
                .filter(candidate -> request.targetMatchStatus() == null || candidate.targetMatchStatus() == request.targetMatchStatus())
                .filter(candidate -> request.riskLevel() == null || candidate.riskLevel() == request.riskLevel())
                .filter(candidate -> request.defaultSelected() == null || candidate.defaultSelected() == request.defaultSelected())
                .filter(candidate -> request.selectable() == null || candidate.selectable() == request.selectable())
                .filter(candidate -> matchesKeyword(candidate, request.keyword()))
                .sorted(sort(request))
                .toList();
    }

    public boolean isAllowedSort(String sortBy) {
        return sortBy == null || sortBy.isBlank() || ALLOWED_SORTS.contains(sortBy.trim());
    }

    private Comparator<DependencyAutoFixCandidateResponse> sort(DependencyAutoFixCandidateListRequest request) {
        Comparator<DependencyAutoFixCandidateResponse> comparator = switch (normalize(request.sortBy())) {
            case "dependencyName" -> Comparator.comparing(DependencyAutoFixCandidateResponse::dependencyName, nullSafeString());
            case "targetMatchStatus" -> Comparator.comparing(candidate -> candidate.targetMatchStatus().name());
            case "installPackageName" -> Comparator.comparing(DependencyAutoFixCandidateResponse::installPackageName, nullSafeString());
            case "defaultSelected" -> Comparator.comparing(DependencyAutoFixCandidateResponse::defaultSelected);
            case "selectable" -> Comparator.comparing(DependencyAutoFixCandidateResponse::selectable);
            case "riskLevel" -> Comparator.comparingInt(candidate -> riskRank(candidate.riskLevel()));
            default -> Comparator.comparing(DependencyAutoFixCandidateResponse::resultItemId);
        };
        if (!"asc".equalsIgnoreCase(request.sortDirection())) {
            comparator = comparator.reversed();
        }
        return comparator.thenComparing(DependencyAutoFixCandidateResponse::resultItemId);
    }

    private Comparator<String> nullSafeString() {
        return Comparator.nullsLast(String::compareToIgnoreCase);
    }

    private boolean matchesKeyword(DependencyAutoFixCandidateResponse candidate, String keyword) {
        if (!hasText(keyword)) {
            return true;
        }
        String text = keyword.trim().toLowerCase(Locale.ROOT);
        return contains(candidate.dependencyName(), text)
                || contains(candidate.installPackageName(), text)
                || contains(candidate.sourceProviderPackage(), text)
                || contains(candidate.targetProviderPackage(), text)
                || contains(candidate.reason(), text);
    }

    private boolean contains(String value, String keyword) {
        return value != null && value.toLowerCase(Locale.ROOT).contains(keyword);
    }

    private int riskRank(DependencyRiskLevel riskLevel) {
        return switch (riskLevel) {
            case CRITICAL -> 6;
            case HIGH -> 5;
            case MEDIUM -> 4;
            case LOW -> 3;
            case INFO -> 2;
            case COMMENT -> 1;
        };
    }

    private String majorVersion(String version) {
        if (!hasText(version)) {
            return null;
        }
        String trimmed = version.trim();
        StringBuilder value = new StringBuilder();
        for (int i = 0; i < trimmed.length(); i++) {
            char ch = trimmed.charAt(i);
            if (Character.isDigit(ch)) {
                value.append(ch);
                continue;
            }
            if (!value.isEmpty()) {
                break;
            }
        }
        return value.isEmpty() ? null : value.toString();
    }

    private String normalize(String value) {
        return value == null || value.isBlank() ? "riskLevel" : value.trim();
    }

    private String firstNonBlank(String first, String second) {
        return hasText(first) ? first.trim() : hasText(second) ? second.trim() : null;
    }

    private String blankToNull(String value) {
        return hasText(value) ? value.trim() : null;
    }

    private boolean hasText(String value) {
        return value != null && !value.isBlank();
    }
}
