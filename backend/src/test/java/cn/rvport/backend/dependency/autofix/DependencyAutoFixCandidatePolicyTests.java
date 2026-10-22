package cn.rvport.backend.dependency.autofix;

import static org.assertj.core.api.Assertions.assertThat;

import cn.rvport.backend.dependency.DependencyAnalysisResultItemView;
import cn.rvport.backend.dependency.DependencyConfidence;
import cn.rvport.backend.dependency.DependencyRiskLevel;
import cn.rvport.backend.dependency.DependencyTargetMatchStatus;
import cn.rvport.backend.dependency.DependencyType;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class DependencyAutoFixCandidatePolicyTests {

    private final DependencyAutoFixCandidatePolicy policy = new DependencyAutoFixCandidatePolicy();

    @Test
    void mediumRiskTargetPackageIsDefaultSelected() {
        DependencyAutoFixCandidateResponse candidate = policy.candidate(item(
                DependencyRiskLevel.MEDIUM,
                DependencyTargetMatchStatus.REPO_AVAILABLE,
                "zlib-devel",
                "1.2.13-1",
                "zlib-devel",
                "1.2.13-2"
        ));

        assertThat(candidate.selectable()).isTrue();
        assertThat(candidate.defaultSelected()).isTrue();
        assertThat(candidate.installPackageName()).isEqualTo("zlib-devel");
        assertThat(candidate.installVersionConstraint()).isEqualTo("1.2.13-2");
    }

    @Test
    void highRiskSourcePackageIsSelectableButNotDefaultSelected() {
        DependencyAutoFixCandidateResponse candidate = policy.candidate(item(
                DependencyRiskLevel.HIGH,
                DependencyTargetMatchStatus.TARGET_OLDER,
                "gcc",
                "12.3.1-1",
                null,
                null
        ));

        assertThat(candidate.selectable()).isTrue();
        assertThat(candidate.defaultSelected()).isFalse();
        assertThat(candidate.installPackageName()).isEqualTo("gcc");
        assertThat(candidate.installVersionConstraint()).isEqualTo("12");
    }

    @Test
    void lowRiskAndMissingPackageAreNotSelectable() {
        DependencyAutoFixCandidateResponse low = policy.candidate(item(
                DependencyRiskLevel.LOW,
                DependencyTargetMatchStatus.TARGET_NEWER,
                "make",
                "4.3",
                "make",
                "4.4"
        ));
        DependencyAutoFixCandidateResponse missing = policy.candidate(item(
                DependencyRiskLevel.MEDIUM,
                DependencyTargetMatchStatus.MISSING,
                null,
                null,
                null,
                null
        ));

        assertThat(low.selectable()).isFalse();
        assertThat(missing.selectable()).isFalse();
    }

    @Test
    void filtersSelectableAndRiskLevelThenSortsByRisk() {
        List<DependencyAutoFixCandidateResponse> candidates = policy.filterAndSort(List.of(
                policy.candidate(item(DependencyRiskLevel.MEDIUM, DependencyTargetMatchStatus.REPO_AVAILABLE, "zlib", "1.2", "zlib", "1.2")),
                policy.candidate(item(DependencyRiskLevel.HIGH, DependencyTargetMatchStatus.TARGET_OLDER, "gcc", "12", null, null)),
                policy.candidate(item(DependencyRiskLevel.LOW, DependencyTargetMatchStatus.TARGET_NEWER, "make", "4", "make", "4"))
        ), new DependencyAutoFixCandidateListRequest(
                1,
                20,
                null,
                null,
                DependencyRiskLevel.HIGH,
                null,
                true,
                null,
                "riskLevel",
                "desc"
        ));

        assertThat(candidates)
                .extracting(DependencyAutoFixCandidateResponse::installPackageName)
                .containsExactly("gcc");
    }

    @Test
    void supportsEverySortAndFilterWithNullSafeValues() {
        DependencyAutoFixCandidateResponse medium = policy.candidate(item(
                DependencyRiskLevel.MEDIUM, DependencyTargetMatchStatus.REPO_AVAILABLE,
                " zlib ", "1.2", " zlib-target ", " "));
        DependencyAutoFixCandidateResponse high = policy.candidate(item(
                DependencyRiskLevel.HIGH, DependencyTargetMatchStatus.TARGET_OLDER,
                " gcc ", "release-14.2", null, null));
        DependencyAutoFixCandidateResponse critical = policy.candidate(item(
                DependencyRiskLevel.CRITICAL, DependencyTargetMatchStatus.MISSING,
                null, null, null, null));
        List<DependencyAutoFixCandidateResponse> all = List.of(medium, high, critical);

        assertThat(medium.installPackageName()).isEqualTo("zlib-target");
        assertThat(medium.installVersionConstraint()).isNull();
        assertThat(high.installPackageName()).isEqualTo("gcc");
        assertThat(high.installVersionConstraint()).isEqualTo("14");

        for (String sort : List.of("createdAt", "dependencyName", "targetMatchStatus",
                "installPackageName", "defaultSelected", "selectable", "riskLevel")) {
            assertThat(policy.filterAndSort(all, request(sort, "asc", null, null, null, null, true, null)))
                    .hasSize(2);
        }
        assertThat(policy.filterAndSort(all, request("dependencyName", "desc", medium.dependencyType(),
                medium.targetMatchStatus(), DependencyRiskLevel.MEDIUM, true, true, "ZLIB")))
                .containsExactly(medium);
        assertThat(policy.filterAndSort(all, request("riskLevel", null, null, null, null, null, true, "gcc")))
                .containsExactly(high);
    }

    @Test
    void validatesSortNamesAndCoversAllRiskRanksAndVersionShapes() {
        assertThat(policy.isAllowedSort(null)).isTrue();
        assertThat(policy.isAllowedSort(" ")).isTrue();
        assertThat(policy.isAllowedSort(" riskLevel ")).isTrue();
        assertThat(policy.isAllowedSort("unknown")).isFalse();

        List<DependencyAutoFixCandidateResponse> candidates = List.of(
                policy.candidate(item(DependencyRiskLevel.CRITICAL, DependencyTargetMatchStatus.MISSING, null, null, null, null)),
                policy.candidate(item(DependencyRiskLevel.HIGH, DependencyTargetMatchStatus.TARGET_OLDER, "high", "version", null, null)),
                policy.candidate(item(DependencyRiskLevel.MEDIUM, DependencyTargetMatchStatus.REPO_AVAILABLE, "medium", "2", "medium", "2")),
                policy.candidate(item(DependencyRiskLevel.LOW, DependencyTargetMatchStatus.TARGET_NEWER, "low", "1", "low", "2")),
                policy.candidate(item(DependencyRiskLevel.INFO, DependencyTargetMatchStatus.SAME_MAJOR, "info", "1", "info", "1")),
                policy.candidate(item(DependencyRiskLevel.COMMENT, DependencyTargetMatchStatus.MANUAL_CONFIRM_REQUIRED, "comment", "1", "comment", "1"))
        );

        assertThat(policy.filterAndSort(candidates, request(null, "asc", null, null, null, null, true, null)))
                .extracting(DependencyAutoFixCandidateResponse::riskLevel)
                .containsExactly(DependencyRiskLevel.MEDIUM, DependencyRiskLevel.HIGH);
        assertThat(policy.filterAndSort(candidates, request(null, "asc", null, null, null, null, false, null)))
                .extracting(DependencyAutoFixCandidateResponse::riskLevel)
                .containsExactly(DependencyRiskLevel.COMMENT, DependencyRiskLevel.INFO,
                        DependencyRiskLevel.LOW, DependencyRiskLevel.CRITICAL);
        assertThat(candidates.get(1).installVersionConstraint()).isNull();
    }

    @Test
    void keywordCanMatchEachDisplayedFieldAndRejectsUnrelatedText() {
        DependencyAutoFixCandidateResponse candidate = new DependencyAutoFixCandidateResponse(
                UUID.randomUUID(), DependencyType.BUILD_PACKAGE, "dependency-name", "1",
                DependencyRiskLevel.MEDIUM, DependencyTargetMatchStatus.REPO_AVAILABLE,
                "source-provider", "2", "target-provider", "3", "install-name", "3",
                true, true, "distinct-reason");

        for (String keyword : List.of("dependency", "install", "source", "target", "reason")) {
            assertThat(policy.filterAndSort(List.of(candidate), request(
                    "riskLevel", "asc", null, null, null, null, null, keyword)))
                    .containsExactly(candidate);
        }
        assertThat(policy.filterAndSort(List.of(candidate), request(
                "riskLevel", "asc", null, null, null, null, null, "absent"))).isEmpty();
        assertThat(policy.filterAndSort(List.of(candidate), request(
                " ", "asc", null, null, null, null, null, " "))).containsExactly(candidate);
    }

    @Test
    void highRiskPrefersTargetPackageWhenBothProviderNamesExist() {
        DependencyAutoFixCandidateResponse candidate = policy.candidate(item(
                DependencyRiskLevel.HIGH, DependencyTargetMatchStatus.TARGET_OLDER,
                "source-gcc", "release-14", "target-gcc", "13"));

        assertThat(candidate.installPackageName()).isEqualTo("target-gcc");
        assertThat(candidate.installVersionConstraint()).isEqualTo("14");
    }

    private DependencyAutoFixCandidateListRequest request(
            String sortBy,
            String direction,
            cn.rvport.backend.dependency.DependencyType type,
            DependencyTargetMatchStatus status,
            DependencyRiskLevel risk,
            Boolean defaultSelected,
            Boolean selectable,
            String keyword
    ) {
        return new DependencyAutoFixCandidateListRequest(1, 100, type, status, risk, defaultSelected,
                selectable, keyword, sortBy, direction);
    }

    private DependencyAnalysisResultItemView item(
            DependencyRiskLevel riskLevel,
            DependencyTargetMatchStatus targetMatchStatus,
            String sourceProviderPackage,
            String sourceProviderVersion,
            String targetProviderPackage,
            String targetProviderVersion
    ) {
        return new DependencyAnalysisResultItemView(
                UUID.randomUUID(),
                UUID.randomUUID(),
                UUID.randomUUID(),
                UUID.randomUUID(),
                UUID.randomUUID(),
                DependencyType.BUILD_PACKAGE,
                sourceProviderPackage == null ? "unknown" : sourceProviderPackage,
                null,
                sourceProviderPackage,
                sourceProviderVersion,
                null,
                targetProviderPackage,
                targetProviderVersion,
                null,
                null,
                null,
                targetMatchStatus,
                riskLevel,
                "package:" + (sourceProviderPackage == null ? "unknown" : sourceProviderPackage),
                "建议安装目标环境可用软件包",
                DependencyConfidence.HIGH,
                Map.of(),
                OffsetDateTime.now()
        );
    }
}
