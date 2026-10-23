package cn.rvport.backend.testcomparison.runtime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.when;

import cn.rvport.backend.artifact.StoredArtifactService;
import cn.rvport.backend.automatedtest.AutomatedTestRunView;
import cn.rvport.backend.automatedtest.TestBatchRole;
import cn.rvport.backend.task.TaskLogService;
import cn.rvport.backend.task.TaskStatus;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ByteArrayResource;

class TestComparisonInputAggregatorTests {

    @Test
    void prefersMergedLogWhenCombinedLogExists() {
        TaskLogService logs = org.mockito.Mockito.mock(TaskLogService.class);
        TestComparisonInputAggregator aggregator = new TestComparisonInputAggregator(
                logs,
                org.mockito.Mockito.mock(StoredArtifactService.class),
                new ObjectMapper()
        );
        UUID taskId = UUID.randomUUID();
        UUID combinedLogId = UUID.randomUUID();
        AutomatedTestRunView run = run(taskId, combinedLogId, UUID.randomUUID(), UUID.randomUUID());
        when(logs.readText(taskId, combinedLogId, 256 * 1024L + 1L)).thenReturn("[STDOUT] ok\n[STDERR] warn\n");

        TestComparisonInputBundle bundle = aggregator.aggregate(run, run);

        Map<?, ?> source = (Map<?, ?>) bundle.payload().get("source");
        assertThat(source.get("mergedLog")).isEqualTo("[STDOUT] ok\n[STDERR] warn\n");
        assertThat(stringObjectMap(source.get("logMaterial"))).containsEntry("primary", "mergedLog")
                .containsEntry("degraded", false);
    }

    @Test
    void fallsBackToSplitLogsForLegacyRunWithoutCombinedLog() {
        TaskLogService logs = org.mockito.Mockito.mock(TaskLogService.class);
        TestComparisonInputAggregator aggregator = new TestComparisonInputAggregator(
                logs,
                org.mockito.Mockito.mock(StoredArtifactService.class),
                new ObjectMapper()
        );
        UUID taskId = UUID.randomUUID();
        UUID stdoutLogId = UUID.randomUUID();
        UUID stderrLogId = UUID.randomUUID();
        AutomatedTestRunView run = run(taskId, null, stdoutLogId, stderrLogId);
        when(logs.readText(taskId, stdoutLogId, 256 * 1024L + 1L)).thenReturn("ok\n");
        when(logs.readText(taskId, stderrLogId, 256 * 1024L + 1L)).thenReturn("warn\n");

        TestComparisonInputBundle bundle = aggregator.aggregate(run, run);

        Map<?, ?> source = (Map<?, ?>) bundle.payload().get("source");
        assertThat(source.get("mergedLog")).isEqualTo("");
        assertThat(source.get("stdout")).isEqualTo("ok\n");
        assertThat(source.get("stderr")).isEqualTo("warn\n");
        assertThat(stringObjectMap(source.get("logMaterial"))).containsEntry("primary", "stdout/stderr")
                .containsEntry("degraded", true);
    }

    @Test
    void aggregatesDifferentSidesAndSanitizesSensitiveLogValues() {
        TaskLogService logs = org.mockito.Mockito.mock(TaskLogService.class);
        TestComparisonInputAggregator aggregator = new TestComparisonInputAggregator(
                logs,
                org.mockito.Mockito.mock(StoredArtifactService.class),
                new ObjectMapper()
        );
        UUID sourceTaskId = UUID.randomUUID();
        UUID targetTaskId = UUID.randomUUID();
        UUID sourceLogId = UUID.randomUUID();
        UUID targetLogId = UUID.randomUUID();
        AutomatedTestRunView source = run(sourceTaskId, sourceLogId, null, null);
        AutomatedTestRunView target = run(targetTaskId, targetLogId, null, null);
        when(logs.readText(sourceTaskId, sourceLogId, 256 * 1024L + 1L))
                .thenReturn("Authorization: Bearer secret-token\napi_key=abc\npassword: hidden\n");
        when(logs.readText(targetTaskId, targetLogId, 256 * 1024L + 1L)).thenReturn(null);

        TestComparisonInputBundle bundle = aggregator.aggregate(source, target);

        Map<?, ?> sourcePayload = (Map<?, ?>) bundle.payload().get("source");
        Map<?, ?> targetPayload = (Map<?, ?>) bundle.payload().get("target");
        assertThat(sourcePayload.get("mergedLog").toString())
                .contains("Bearer [REDACTED]", "api_key=[REDACTED]", "password: [REDACTED]")
                .doesNotContain("secret-token", "abc", "hidden");
        assertThat(targetPayload.get("mergedLog")).isEqualTo("");
        assertThat(bundle.truncated()).isFalse();
        assertThat(bundle.summary()).containsEntry("logMaxBytes", 256 * 1024)
                .containsEntry("reportMaxBytes", 128 * 1024);
    }

    @Test
    void truncatesOversizedUtf8LogAndReportsOriginalByteCount() {
        TaskLogService logs = org.mockito.Mockito.mock(TaskLogService.class);
        TestComparisonInputAggregator aggregator = new TestComparisonInputAggregator(
                logs,
                org.mockito.Mockito.mock(StoredArtifactService.class),
                new ObjectMapper()
        );
        UUID taskId = UUID.randomUUID();
        UUID logId = UUID.randomUUID();
        AutomatedTestRunView run = run(taskId, logId, null, null);
        String oversized = "x".repeat(256 * 1024 + 1);
        when(logs.readText(taskId, logId, 256 * 1024L + 1L)).thenReturn(oversized);

        TestComparisonInputBundle bundle = aggregator.aggregate(run, run);

        Map<?, ?> source = (Map<?, ?>) bundle.payload().get("source");
        assertThat(source.get("mergedLog").toString().getBytes(StandardCharsets.UTF_8)).hasSize(256 * 1024);
        assertThat(bundle.truncated()).isTrue();
        assertThat(stringObjectMap(bundle.summary().get("source.mergedLog")))
                .containsEntry("present", true)
                .containsEntry("truncated", true)
                .containsEntry("bytes", 256 * 1024 + 1);
    }

    @Test
    void handlesAbsentReportsAndReportWithoutArtifact() {
        TestComparisonInputAggregator aggregator = new TestComparisonInputAggregator(
                org.mockito.Mockito.mock(TaskLogService.class),
                org.mockito.Mockito.mock(StoredArtifactService.class),
                new ObjectMapper()
        );
        AutomatedTestRunView absent = runWithReports(null);
        AutomatedTestRunView metadataOnly = runWithReports(List.of(Map.of(
                "path", "result.xml",
                "status", "MISSING",
                "message", "not produced"
        )));

        TestComparisonInputBundle bundle = aggregator.aggregate(absent, metadataOnly);

        Map<?, ?> source = (Map<?, ?>) bundle.payload().get("source");
        Map<?, ?> target = (Map<?, ?>) bundle.payload().get("target");
        assertThat((List<?>) source.get("reports")).isEmpty();
        assertThat((List<?>) target.get("reports")).singleElement().satisfies(item ->
                assertThat(stringObjectMap(item)).containsEntry("content", ""));
        assertThat(stringObjectMap(bundle.summary().get("source.reports")))
                .containsEntry("count", 0)
                .containsEntry("truncated", false);
    }

    @Test
    void readsAndTruncatesReportArtifacts() {
        StoredArtifactService artifacts = org.mockito.Mockito.mock(StoredArtifactService.class);
        TestComparisonInputAggregator aggregator = new TestComparisonInputAggregator(
                org.mockito.Mockito.mock(TaskLogService.class), artifacts, new ObjectMapper());
        UUID normalId = UUID.randomUUID();
        UUID largeId = UUID.randomUUID();
        when(artifacts.download(normalId)).thenReturn(new cn.rvport.backend.artifact.StoredArtifactResource(
                null, new ByteArrayResource("password=secret".getBytes(StandardCharsets.UTF_8))));
        when(artifacts.download(largeId)).thenReturn(new cn.rvport.backend.artifact.StoredArtifactResource(
                null, new ByteArrayResource("r".repeat(128 * 1024 + 1).getBytes(StandardCharsets.UTF_8))));
        AutomatedTestRunView source = runWithReports(List.of(
                Map.of("path", "small.txt", "status", "FOUND", "message", "ok", "artifactId", normalId.toString()),
                Map.of("path", "large.txt", "status", "FOUND", "message", "ok", "artifactId", largeId.toString())
        ));

        TestComparisonInputBundle bundle = aggregator.aggregate(source, runWithReports(List.of()));

        Map<?, ?> sourcePayload = (Map<?, ?>) bundle.payload().get("source");
        List<?> reports = (List<?>) sourcePayload.get("reports");
        assertThat(reports).hasSize(2);
        assertThat(stringObjectMap(reports.get(0))).containsEntry("content", "password=[REDACTED]")
                .containsEntry("truncated", false);
        assertThat(((Map<?, ?>) reports.get(1)).get("content").toString()).hasSize(128 * 1024);
        assertThat(stringObjectMap(reports.get(1))).containsEntry("truncated", true);
        assertThat(bundle.truncated()).isTrue();
    }

    @Test
    void convertsInvalidOrUnreadableReportArtifactToStableReadError() {
        StoredArtifactService artifacts = org.mockito.Mockito.mock(StoredArtifactService.class);
        TestComparisonInputAggregator aggregator = new TestComparisonInputAggregator(
                org.mockito.Mockito.mock(TaskLogService.class), artifacts, new ObjectMapper());
        UUID unreadableId = UUID.randomUUID();
        when(artifacts.download(unreadableId)).thenReturn(new cn.rvport.backend.artifact.StoredArtifactResource(
                null,
                new ByteArrayResource(new byte[0]) {
                    @Override
                    public InputStream getInputStream() throws IOException {
                        throw new IOException("storage detail");
                    }
                }
        ));
        AutomatedTestRunView run = runWithReports(List.of(
                Map.of("path", "bad-id", "status", "FOUND", "message", "", "artifactId", "invalid"),
                Map.of("path", "unreadable", "status", "FOUND", "message", "", "artifactId", unreadableId.toString())
        ));

        TestComparisonInputBundle bundle = aggregator.aggregate(run, runWithReports(List.of()));

        Map<?, ?> source = (Map<?, ?>) bundle.payload().get("source");
        assertThat((List<?>) source.get("reports")).allSatisfy(item ->
                assertThat(stringObjectMap(item))
                        .containsEntry("content", "")
                        .containsEntry("readError", "REPORT_ARTIFACT_READ_FAILED"));
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> stringObjectMap(Object value) {
        return (Map<String, Object>) value;
    }

    private AutomatedTestRunView run(UUID taskId, UUID combinedLogId, UUID stdoutLogId, UUID stderrLogId) {
        return run(taskId, combinedLogId, stdoutLogId, stderrLogId, List.of());
    }

    private AutomatedTestRunView runWithReports(List<Map<String, Object>> reports) {
        return run(UUID.randomUUID(), null, null, null, reports);
    }

    private AutomatedTestRunView run(
            UUID taskId,
            UUID combinedLogId,
            UUID stdoutLogId,
            UUID stderrLogId,
            List<Map<String, Object>> reports
    ) {
        return new AutomatedTestRunView(
                UUID.randomUUID(),
                UUID.randomUUID(),
                taskId,
                UUID.randomUUID(),
                UUID.randomUUID(),
                UUID.randomUUID(),
                1L,
                UUID.randomUUID(),
                TestBatchRole.SOURCE,
                "env",
                "make test",
                "/tmp/project",
                60,
                0,
                null,
                null,
                null,
                TaskStatus.SUCCEEDED,
                stdoutLogId,
                stderrLogId,
                combinedLogId,
                "exitCode=0",
                reports,
                OffsetDateTime.now(),
                OffsetDateTime.now()
        );
    }
}
