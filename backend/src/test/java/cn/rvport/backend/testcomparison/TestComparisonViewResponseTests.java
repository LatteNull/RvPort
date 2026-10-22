package cn.rvport.backend.testcomparison;

import static org.assertj.core.api.Assertions.assertThat;

import cn.rvport.backend.jooq.tables.records.TestComparisonFindingsRecord;
import cn.rvport.backend.jooq.tables.records.TestComparisonRunsRecord;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class TestComparisonViewResponseTests {

    @Test
    void findingViewDefaultsNullRawPayload() {
        TestComparisonFindingsRecord record = new TestComparisonFindingsRecord();
        record.setId(UUID.randomUUID());
        record.setComparisonRunId(UUID.randomUUID());
        record.setSequenceNo(1);
        record.setDifferenceType("REGRESSION");
        record.setSeverity(TestComparisonRiskLevel.HIGH.name());
        record.setTitle("failure");
        record.setCreatedAt(OffsetDateTime.now());

        assertThat(TestComparisonFindingView.from(record, null).rawPayload()).isEmpty();
        assertThat(TestComparisonFindingView.from(record, Map.of("test", "failed")).rawPayload())
                .containsEntry("test", "failed");
    }

    @Test
    void runViewDefaultsNullStatsAndMapsOptionalEnums() {
        TestComparisonRunsRecord record = runRecord();
        TestComparisonRunView empty = TestComparisonRunView.from(record, null, null, null);
        assertThat(empty.inputSummary()).isEmpty();
        assertThat(empty.sourceTestStats()).isEmpty();
        assertThat(empty.targetTestStats()).isEmpty();
        assertThat(empty.overallStatus()).isNull();
        assertThat(empty.riskLevel()).isNull();

        record.setOverallStatus(TestComparisonOverallStatus.EQUIVALENT.name());
        record.setRiskLevel(TestComparisonRiskLevel.LOW.name());
        TestComparisonRunView populated = TestComparisonRunView.from(
                record, Map.of("input", 1), Map.of("passed", 2), Map.of("passed", 2));
        assertThat(populated.overallStatus()).isEqualTo(TestComparisonOverallStatus.EQUIVALENT);
        assertThat(populated.riskLevel()).isEqualTo(TestComparisonRiskLevel.LOW);
        assertThat(populated.inputSummary()).containsEntry("input", 1);
    }

    @Test
    void responsePreservesPresentEnumsAndLeavesMissingEnumsNull() {
        TestComparisonRunsRecord record = runRecord();
        TestComparisonResponse empty = TestComparisonResponse.from(
                TestComparisonRunView.from(record, Map.of(), Map.of(), Map.of()));
        assertThat(empty.overallStatus()).isNull();
        assertThat(empty.riskLevel()).isNull();

        record.setOverallStatus(TestComparisonOverallStatus.DIFFERENT_BLOCKING.name());
        record.setRiskLevel(TestComparisonRiskLevel.HIGH.name());
        TestComparisonResponse populated = TestComparisonResponse.from(
                TestComparisonRunView.from(record, Map.of(), Map.of(), Map.of()));
        assertThat(populated.overallStatus()).isEqualTo("DIFFERENT_BLOCKING");
        assertThat(populated.riskLevel()).isEqualTo("HIGH");
    }

    private TestComparisonRunsRecord runRecord() {
        TestComparisonRunsRecord record = new TestComparisonRunsRecord();
        record.setId(UUID.randomUUID());
        record.setProjectId(UUID.randomUUID());
        record.setTaskId(UUID.randomUUID());
        record.setTestBatchId(UUID.randomUUID());
        record.setSourceTestRunId(UUID.randomUUID());
        record.setTargetTestRunId(UUID.randomUUID());
        record.setStatus(TestComparisonStatus.SUCCEEDED.name());
        record.setInputTruncated(false);
        record.setCreatedAt(OffsetDateTime.now());
        record.setUpdatedAt(OffsetDateTime.now());
        return record;
    }
}
