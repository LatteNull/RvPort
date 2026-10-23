package cn.rvport.backend.testcomparison.runtime;

import cn.rvport.backend.artifact.StoredArtifactService;
import cn.rvport.backend.automatedtest.AutomatedTestRunView;
import cn.rvport.backend.task.TaskLogService;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Component;

@Component
public class TestComparisonInputAggregator {

    private static final int LOG_MAX_BYTES = 256 * 1024;
    private static final int REPORT_MAX_BYTES = 128 * 1024;

    private final TaskLogService taskLogService;
    private final StoredArtifactService storedArtifactService;
    private final ObjectMapper objectMapper;

    public TestComparisonInputAggregator(
            TaskLogService taskLogService,
            StoredArtifactService storedArtifactService,
            ObjectMapper objectMapper
    ) {
        this.taskLogService = taskLogService;
        this.storedArtifactService = storedArtifactService;
        this.objectMapper = objectMapper;
    }

    public TestComparisonInputBundle aggregate(AutomatedTestRunView source, AutomatedTestRunView target) {
        Map<String, Object> summary = new LinkedHashMap<>();
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("schemaVersion", "test-comparison.v1");
        payload.put("source", sidePayload(source, summary, "source"));
        payload.put("target", sidePayload(target, summary, "target"));
        boolean truncated = summary.values().stream()
                .filter(Map.class::isInstance)
                .map(Map.class::cast)
                .anyMatch(item -> Boolean.TRUE.equals(item.get("truncated")));
        summary.put("logMaxBytes", LOG_MAX_BYTES);
        summary.put("reportMaxBytes", REPORT_MAX_BYTES);
        return new TestComparisonInputBundle(payload, truncated, summary);
    }

    private Map<String, Object> sidePayload(AutomatedTestRunView run, Map<String, Object> summary, String side) {
        Map<String, Object> value = new LinkedHashMap<>();
        value.put("testRunId", run.id());
        value.put("taskId", run.taskId());
        value.put("buildRunId", run.buildRunId());
        value.put("sourceRevisionId", run.sourceRevisionId());
        value.put("environmentId", run.environmentId());
        value.put("environmentName", run.environmentName());
        value.put("status", run.status().name());
        value.put("exitCode", run.exitCode());
        value.put("outputSummary", run.outputSummary());
        String mergedLog = readLog(run.taskId(), run.combinedLogId(), summary, side + ".mergedLog");
        boolean mergedPresent = run.combinedLogId() != null && !mergedLog.isBlank();
        value.put("mergedLog", mergedLog);
        value.put("stdout", readLog(run.taskId(), run.stdoutLogId(), summary, side + ".stdout"));
        value.put("stderr", readLog(run.taskId(), run.stderrLogId(), summary, side + ".stderr"));
        value.put("logMaterial", Map.of(
                "primary", mergedPresent ? "mergedLog" : "stdout/stderr",
                "degraded", !mergedPresent,
                "degradeReason", mergedPresent ? "" : "MERGED_LOG_MISSING"
        ));
        summary.put(side + ".logMaterial", Map.of(
                "primary", mergedPresent ? "mergedLog" : "stdout/stderr",
                "degraded", !mergedPresent
        ));
        value.put("reports", reportPayloads(run.reportArtifacts(), summary, side + ".reports"));
        return value;
    }

    private String readLog(UUID taskId, UUID logId, Map<String, Object> summary, String key) {
        if (logId == null) {
            summary.put(key, Map.of("present", false, "truncated", false, "bytes", 0));
            return "";
        }
        String text = taskLogService.readText(taskId, logId, LOG_MAX_BYTES + 1L);
        if (text == null) {
            text = "";
        }
        byte[] bytes = text.getBytes(StandardCharsets.UTF_8);
        boolean truncated = bytes.length > LOG_MAX_BYTES;
        String value = truncated ? new String(bytes, 0, LOG_MAX_BYTES, StandardCharsets.UTF_8) : text;
        summary.put(key, Map.of("present", true, "truncated", truncated, "bytes", bytes.length));
        return sanitize(value);
    }

    private List<Map<String, Object>> reportPayloads(List<Map<String, Object>> reports, Map<String, Object> summary, String key) {
        if (reports == null || reports.isEmpty()) {
            summary.put(key, Map.of("count", 0, "truncated", false));
            return List.of();
        }
        return reports.stream()
                .map(report -> reportPayload(report, summary, key))
                .toList();
    }

    private Map<String, Object> reportPayload(Map<String, Object> report, Map<String, Object> summary, String key) {
        Map<String, Object> value = new LinkedHashMap<>();
        value.put("path", report.get("path"));
        value.put("status", report.get("status"));
        value.put("message", report.get("message"));
        Object artifactId = report.get("artifactId");
        if (artifactId == null) {
            value.put("content", "");
            return value;
        }
        try {
            UUID id = UUID.fromString(String.valueOf(artifactId));
            var resource = storedArtifactService.download(id).resource();
            byte[] bytes = resource.getInputStream().readNBytes(REPORT_MAX_BYTES + 1);
            boolean truncated = bytes.length > REPORT_MAX_BYTES;
            value.put("artifactId", id);
            value.put("content", sanitize(new String(bytes, 0, truncated ? REPORT_MAX_BYTES : bytes.length, StandardCharsets.UTF_8)));
            value.put("truncated", truncated);
            summary.put(key + "." + id, Map.of("truncated", truncated, "bytes", bytes.length));
        } catch (IOException | IllegalArgumentException ex) {
            value.put("content", "");
            value.put("readError", "REPORT_ARTIFACT_READ_FAILED");
        }
        return value;
    }

    private String sanitize(String text) {
        if (text == null || text.isBlank()) {
            return "";
        }
        return text
                .replaceAll("(?i)(authorization:\\s*bearer\\s+)[^\\s]+", "$1[REDACTED]")
                .replaceAll("(?i)(api[-_ ]?key[=:]\\s*)[^\\s]+", "$1[REDACTED]")
                .replaceAll("(?i)(password[=:]\\s*)[^\\s]+", "$1[REDACTED]");
    }
}
