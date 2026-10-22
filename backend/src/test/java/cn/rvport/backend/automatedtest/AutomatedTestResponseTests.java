package cn.rvport.backend.automatedtest;

import static org.assertj.core.api.Assertions.assertThat;

import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.testcomparison.TestComparisonOverallStatus;
import cn.rvport.backend.testcomparison.TestComparisonRiskLevel;
import cn.rvport.backend.testcomparison.TestComparisonRunView;
import cn.rvport.backend.testcomparison.TestComparisonStatus;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class AutomatedTestResponseTests {

    @Test
    void exposesCombinedLogIdAsMergedLogReference() {
        UUID combinedLogId = UUID.randomUUID();
        AutomatedTestRunView view = new AutomatedTestRunView(
                UUID.randomUUID(),
                UUID.randomUUID(),
                UUID.randomUUID(),
                UUID.randomUUID(),
                UUID.randomUUID(),
                UUID.randomUUID(),
                1L,
                UUID.randomUUID(),
                TestBatchRole.SOURCE,
                "x86",
                "make test",
                "/workspace",
                60,
                0,
                1,
                0,
                0,
                TaskStatus.SUCCEEDED,
                UUID.randomUUID(),
                UUID.randomUUID(),
                combinedLogId,
                "ok",
                List.of(Map.of("type", "summary")),
                OffsetDateTime.now(),
                OffsetDateTime.now()
        );

        AutomatedTestResponse response = AutomatedTestResponse.from(view);

        assertThat(response.combinedLogId()).isEqualTo(combinedLogId);
    }

    @Test
    void mapsCurrentEnvironmentAndAvailableComparisonDetails() {
        AutomatedTestRunView view = view(7L, TestBatchRole.TARGET);
        UUID comparisonId = UUID.randomUUID();
        TestComparisonRunView comparison = new TestComparisonRunView(
                comparisonId, view.projectId(), UUID.randomUUID(), view.testBatchId(), view.id(), UUID.randomUUID(),
                TestComparisonStatus.UNAVAILABLE, TestComparisonOverallStatus.INCONCLUSIVE,
                TestComparisonRiskLevel.INFO, BigDecimal.ZERO, "summary", "recommendation",
                "MODEL_MISSING", "not configured", null, null, false, Map.of(), Map.of(), Map.of(),
                null, OffsetDateTime.now(), null, null, OffsetDateTime.now());

        AutomatedTestResponse response = AutomatedTestResponse.from(view, 7L, comparison);

        assertThat(response.currentRuntimeEnvironment()).isTrue();
        assertThat(response.testBatchRole()).isEqualTo("TARGET");
        assertThat(response.comparisonId()).isEqualTo(comparisonId);
        assertThat(response.comparisonStatus()).isEqualTo("UNAVAILABLE");
        assertThat(response.comparisonUnavailableCode()).isEqualTo("MODEL_MISSING");
        assertThat(response.comparisonUnavailableMessage()).isEqualTo("not configured");
    }

    @Test
    void treatsMissingOrDifferentEnvironmentVersionAsStaleAndAllowsMissingRole() {
        assertThat(AutomatedTestResponse.from(view(null, null), 0L).currentRuntimeEnvironment()).isFalse();
        AutomatedTestResponse stale = AutomatedTestResponse.from(view(6L, null), 7L);
        assertThat(stale.currentRuntimeEnvironment()).isFalse();
        assertThat(stale.testBatchRole()).isNull();
    }

    private AutomatedTestRunView view(Long environmentVersion, TestBatchRole role) {
        return new AutomatedTestRunView(
                UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(),
                UUID.randomUUID(), environmentVersion, UUID.randomUUID(), role, "env", "make test", null,
                60, 0, 1, 0, 0, TaskStatus.SUCCEEDED, null, null, null, "ok", List.of(),
                OffsetDateTime.now(), OffsetDateTime.now());
    }
}
