package cn.rvport.backend.analysis;

import static org.assertj.core.api.Assertions.assertThat;

import cn.rvport.backend.config.RvPortProperties;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class SpecializedAnalysisValueObjectTests {

    @Test
    void listRequestsNormalizeDefaultsFiltersAndSorts() {
        var defaults = new SpecializedAnalysisListRequest(null, null, " ", null, "bad", "desc");
        var filtered = new SpecializedAnalysisListRequest(2, 200, " partial ", " risk ", "findingCount", "ASC");
        var findings = new SpecializedFindingListRequest(null, null, " high ", " complete ", null, null, null,
                null, "startLine", "asc");

        assertThat(defaults.normalizedPage()).isEqualTo(1);
        assertThat(defaults.normalizedPageSize()).isEqualTo(20);
        assertThat(defaults.normalizedSortBy()).isEqualTo("createdAt");
        assertThat(defaults.normalizedStatus()).isNull();
        assertThat(filtered.normalizedStatus()).isEqualTo("PARTIAL");
        assertThat(filtered.normalizedVerdict()).isEqualTo("RISK");
        assertThat(filtered.ascending()).isTrue();
        assertThat(findings.normalizedSeverity()).isEqualTo("HIGH");
        assertThat(findings.normalizedStatus()).isEqualTo("COMPLETE");
        assertThat(findings.normalizedSortBy()).isEqualTo("startLine");
        assertThat(new SpecializedAnalysisListRequest(-1, 1000, "running", "risk", "status", "asc")
                .normalizedPageSize()).isEqualTo(200);
        assertThat(new SpecializedFindingListRequest(-1, 1000, null, null, null, null, null, null,
                "severity", "ASC").normalizedPageSize()).isEqualTo(200);
        assertThat(new SpecializedFindingListRequest(-1, 50, null, null, null, null, null, null,
                "severity", "ASC").normalizedPage()).isEqualTo(1);
        assertThat(new SpecializedFindingListRequest(1, 50, null, null, null, null, null, null,
                "severity", "ASC").normalizedPageSize()).isEqualTo(50);
        assertThat(new SpecializedFindingListRequest(-1, 1000, null, null, null, null, null, null,
                "severity", "ASC").ascending()).isTrue();
        var boundary = new SpecializedFindingListRequest(2, 0, null, " ", null, null, null, null,
                "unknown", "desc");
        assertThat(boundary.normalizedPage()).isEqualTo(2);
        assertThat(boundary.normalizedPageSize()).isEqualTo(1);
        assertThat(boundary.normalizedSortBy()).isEqualTo("createdAt");
        assertThat(boundary.normalizedSeverity()).isNull();
        assertThat(boundary.normalizedStatus()).isNull();
        assertThat(boundary.ascending()).isFalse();
        assertThat(new SpecializedFindingListRequest(1, 20, null, null, null, null, null, null,
                null, null).normalizedSortBy()).isEqualTo("createdAt");
        assertThat(new SpecializedFindingListRequest(1, 20, null, null, null, null, null, null,
                null, null).ascending()).isFalse();
        var runBoundary = new SpecializedAnalysisListRequest(2, 0, null, " ", "unknown", null);
        assertThat(runBoundary.normalizedPage()).isEqualTo(2);
        assertThat(runBoundary.normalizedPageSize()).isEqualTo(1);
        assertThat(runBoundary.normalizedSortBy()).isEqualTo("createdAt");
        assertThat(runBoundary.normalizedStatus()).isNull();
        assertThat(runBoundary.normalizedVerdict()).isNull();
    }

    @Test
    void responsesExposeCurrentAndStaleSourceRevisionState() {
        UUID source = UUID.randomUUID();
        SpecializedAnalysisRunView run = run(source);

        assertThat(SpecializedAnalysisResponse.from(run, source).currentSourceRevision()).isTrue();
        assertThat(SpecializedAnalysisResponse.from(run, UUID.randomUUID()).staleReasons())
                .containsExactly("SOURCE_REVISION_CHANGED");
    }

    @Test
    void statusesDistinguishPublishedAndTerminalResults() {
        assertThat(SpecializedAnalysisStatus.values()).allSatisfy(status -> {
            boolean expectedTerminal = switch (status) {
                case COMPLETE, COMPLETE_WITH_RISK, PARTIAL, FAILED, CANCELLED, TIMEOUT -> true;
                default -> false;
            };
            boolean expectedPublished = switch (status) {
                case COMPLETE, COMPLETE_WITH_RISK, PARTIAL -> true;
                default -> false;
            };
            assertThat(status.terminal()).isEqualTo(expectedTerminal);
            assertThat(status.publishedResult()).isEqualTo(expectedPublished);
        });
        assertThat(SpecializedAnalyzerType.FLOATING_POINT.displayName()).contains("浮点");
        assertThat(SpecializedAnalyzerType.MEMORY_ORDER.displayName()).contains("内存序");
    }

    @Test
    void frontendOutputBudgetHasDefaultAndWorkerHardLimit() {
        var defaults = new RvPortProperties.SpecializedAnalysis(null, null, null, null, null,
                null, null, null, null, null, null, null, null, null);
        var capped = new RvPortProperties.SpecializedAnalysis(null, null, null, null,
                2L * 1024L * 1024L * 1024L, null, null, null, null, null, null, null, null, null);

        assertThat(defaults.floatingFrontendOutputBytes()).isEqualTo(512L * 1024L * 1024L);
        assertThat(capped.floatingFrontendOutputBytes()).isEqualTo(1024L * 1024L * 1024L);
    }

    private SpecializedAnalysisRunView run(UUID source) {
        OffsetDateTime now = OffsetDateTime.now();
        return new SpecializedAnalysisRunView(UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(),
                SpecializedAnalyzerType.FLOATING_POINT, source, UUID.randomUUID(), "a".repeat(64), 1L, "0.5.0",
                "1.4", "2.0", null, SpecializedAnalysisStatus.COMPLETE, "analyzed", 0, Map.of(),
                UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), null, 1, 0, 0, UUID.randomUUID(),
                now, now, now, now);
    }
}
