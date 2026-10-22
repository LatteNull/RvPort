package cn.rvport.backend.project;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import java.time.OffsetDateTime;
import org.junit.jupiter.api.Test;

class ProjectValueObjectTests {

    @Test
    void projectListRequestDefaultsAndPreservesPagination() {
        ProjectListRequest defaults = new ProjectListRequest(null, null, null, null, null);
        ProjectListRequest explicit = new ProjectListRequest(null, null, null, 3, 50);

        assertThat(defaults.normalizedPage()).isEqualTo(1);
        assertThat(defaults.normalizedPageSize()).isEqualTo(20);
        assertThat(explicit.normalizedPage()).isEqualTo(3);
        assertThat(explicit.normalizedPageSize()).isEqualTo(50);
    }

    @Test
    void overviewCollectionsAreNeverNullAndAreDefensivelyCopied() {
        ProjectOverviewResponse empty = new ProjectOverviewResponse(null, null, null, null, 0);
        ProjectOverviewResponse.WorkflowResponse emptyWorkflow = new ProjectOverviewResponse.WorkflowResponse(null, null);
        var stage = new ProjectOverviewResponse.WorkflowStageResponse(
                "env", ProjectOverviewResponse.WorkflowStageStatus.DONE, "ready");
        ProjectOverviewResponse.WorkflowResponse workflow = new ProjectOverviewResponse.WorkflowResponse("env", List.of(stage));

        assertThat(empty.recentTasks()).isEmpty();
        assertThat(emptyWorkflow.stages()).isEmpty();
        assertThat(workflow.stages()).containsExactly(stage);
    }

    @Test
    void projectSummaryKeepsLatestScanTimestampAndUpdatesIndependentFields() {
        OffsetDateTime older = OffsetDateTime.parse("2026-01-01T00:00:00Z");
        OffsetDateTime newer = OffsetDateTime.parse("2026-01-02T00:00:00Z");

        ProjectSummaryView summary = ProjectSummaryView.empty()
                .withLatestScanAt(null)
                .withLatestScanAt(newer)
                .withLatestScanAt(older)
                .withHighRiskCount(3)
                .withLatestBuildStatus("SUCCEEDED")
                .withLatestTestStatus("FAILED");

        assertThat(summary.highRiskCount()).isEqualTo(3);
        assertThat(summary.latestScanAt()).isEqualTo(newer);
        assertThat(summary.latestBuildStatus()).isEqualTo("SUCCEEDED");
        assertThat(summary.latestTestStatus()).isEqualTo("FAILED");
        assertThat(summary.withLatestScanAt(newer.plusDays(1)).latestScanAt()).isEqualTo(newer.plusDays(1));
        assertThat(summary.withLatestScanAt(newer).latestScanAt()).isEqualTo(newer);
    }
}
