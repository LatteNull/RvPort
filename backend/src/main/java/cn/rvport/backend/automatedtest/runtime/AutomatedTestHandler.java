package cn.rvport.backend.automatedtest.runtime;

import cn.rvport.backend.archive.ArchiveCandidateRegistrar;
import cn.rvport.backend.artifact.StoredArtifactRepository;
import cn.rvport.backend.artifact.StoredArtifactOwnerType;
import cn.rvport.backend.artifact.StoredArtifactService;
import cn.rvport.backend.artifact.StoredArtifactView;
import cn.rvport.backend.automatedtest.AutomatedTestInput;
import cn.rvport.backend.automatedtest.AutomatedTestReportTarget;
import cn.rvport.backend.automatedtest.AutomatedTestReportTargetType;
import cn.rvport.backend.automatedtest.AutomatedTestRepository;
import cn.rvport.backend.automatedtest.AutomatedTestRunView;
import cn.rvport.backend.environment.runtime.EnvironmentTaskInput;
import cn.rvport.backend.environment.runtime.SshCommandResult;
import cn.rvport.backend.environment.runtime.SshRuntimeException;
import cn.rvport.backend.environment.runtime.SshRuntimeService;
import cn.rvport.backend.task.RvPortTaskTypes;
import cn.rvport.backend.task.TaskErrorCode;
import cn.rvport.backend.task.TaskExecutionException;
import cn.rvport.backend.task.TaskLogRepository;
import cn.rvport.backend.task.TaskLogResponse;
import cn.rvport.backend.task.TaskLogType;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.testcomparison.TestComparisonService;
import cn.rvport.backend.worker.TaskExecutionContext;
import cn.rvport.backend.worker.TaskHandler;
import cn.rvport.backend.worker.TaskHandlerResult;
import cn.rvport.backend.worker.TaskCancelledException;
import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Component;

@Component
public class AutomatedTestHandler implements TaskHandler {

    private static final int REPORT_DIRECTORY_MAX_DEPTH = 4;
    private static final int REPORT_DIRECTORY_MAX_FILES = 100;
    private static final int REPORT_FILE_MAX_BYTES = 5 * 1024 * 1024;
    private static final int REPORT_TOTAL_MAX_BYTES = 50 * 1024 * 1024;

    private final AutomatedTestRepository repository;
    private final SshRuntimeService sshRuntimeService;
    private final StoredArtifactService storedArtifactService;
    private final StoredArtifactRepository storedArtifactRepository;
    private final TaskLogRepository taskLogRepository;
    private final TestComparisonService testComparisonService;
    private final ArchiveCandidateRegistrar archiveCandidateRegistrar;

    public AutomatedTestHandler(
            AutomatedTestRepository repository,
            SshRuntimeService sshRuntimeService,
            StoredArtifactService storedArtifactService,
            StoredArtifactRepository storedArtifactRepository,
            TaskLogRepository taskLogRepository,
            TestComparisonService testComparisonService,
            ArchiveCandidateRegistrar archiveCandidateRegistrar
    ) {
        this.repository = repository;
        this.sshRuntimeService = sshRuntimeService;
        this.storedArtifactService = storedArtifactService;
        this.storedArtifactRepository = storedArtifactRepository;
        this.taskLogRepository = taskLogRepository;
        this.testComparisonService = testComparisonService;
        this.archiveCandidateRegistrar = archiveCandidateRegistrar;
    }

    @Override
    public String taskType() {
        return RvPortTaskTypes.AUTOMATED_TEST;
    }

    @Override
    public TaskHandlerResult handle(TaskExecutionContext context) {
        AutomatedTestInput input = context.input(AutomatedTestInput.class);
        UUID testRunId = input.testRunId();
        if (testRunId == null) {
            testRunId = repository.findByTaskId(context.task().id())
                    .orElseThrow(() -> new TaskExecutionException(TaskErrorCode.RESOURCE_NOT_FOUND, "自动化测试记录不存在", null))
                    .id();
        }
        UUID runId = testRunId;
        context.publish(() -> { repository.markRunning(runId); return null; });
        context.progress(10, "开始执行自动化测试");
        SshCommandResult result = null;
        List<Map<String, Object>> reportArtifacts = List.of();
        try {
            result = sshRuntimeService.executeRemote(
                    environmentTaskInput(input),
                    sshRuntimeService.temporaryScriptCommand(input.workingDirectory()),
                    testScript(input),
                    true,
                    input.timeoutSeconds(),
                    context
            );
            context.progress(80, "测试命令执行完成，开始回收报告");
            reportArtifacts = collectReports(input, testRunId, context);
            TaskStatus status = result.exitCode() == 0 ? TaskStatus.SUCCEEDED : TaskStatus.FAILED;
            publishResult(context, testRunId, status, result, reportArtifacts);
            if (result.exitCode() != 0) {
                throw new TaskExecutionException(TaskErrorCode.REMOTE_COMMAND_FAILED, "自动化测试执行失败", null);
            }
            context.progress(95, "自动化测试完成");
            return TaskHandlerResult.success("自动化测试完成");
        } catch (TaskExecutionException ex) {
            finishFailed(testRunId, result, reportArtifacts, context, ex.getMessage());
            throw ex;
        } catch (TaskCancelledException ex) {
            finishWithStatus(testRunId, TaskStatus.CANCELLED, result, reportArtifacts, context, "任务已取消");
            throw ex;
        } catch (SshRuntimeException ex) {
            finishWithStatus(testRunId, timeout(ex) ? TaskStatus.TIMEOUT : TaskStatus.FAILED,
                    result, reportArtifacts, context, "自动化测试 SSH 执行失败");
            throw new TaskExecutionException(TaskErrorCode.REMOTE_COMMAND_FAILED, "自动化测试 SSH 执行失败", ex);
        }
    }

    private void publishResult(TaskExecutionContext context, UUID testRunId, TaskStatus status,
            SshCommandResult result, List<Map<String, Object>> reportArtifacts) {
        context.publish(() -> {
            repository.finish(
                    testRunId,
                    status,
                    result.exitCode(),
                    latestLogId(context.task().id(), TaskLogType.STDOUT),
                    latestLogId(context.task().id(), TaskLogType.STDERR),
                    latestLogId(context.task().id(), TaskLogType.COMBINED),
                    outputSummary(result, reportArtifacts),
                    reportArtifacts
            );
            AutomatedTestRunView finished = repository.findById(testRunId).orElse(null);
            if (finished != null) {
                archiveCandidateRegistrar.registerAutomatedTest(
                        finished,
                        archiveSummary(finished, result, reportArtifacts),
                        collectedArtifacts(reportArtifacts)
                );
            }
            testComparisonService.onAutomatedTestFinished(testRunId);
            return null;
        });
    }

    private EnvironmentTaskInput environmentTaskInput(AutomatedTestInput input) {
        return new EnvironmentTaskInput(
                input.projectId(),
                input.environmentId(),
                null,
                input.timeoutSeconds(),
                "CUSTOM_BASH",
                null,
                null,
                input.workingDirectory(),
                null,
                null,
                null,
                null
        );
    }

    private String testScript(AutomatedTestInput input) {
        StringBuilder script = new StringBuilder();
        script.append("set +e\n");
        if (input.environmentVariables() != null) {
            input.environmentVariables().forEach((name, value) ->
                    script.append("export ").append(name).append("=").append(shellQuote(value == null ? "" : value)).append("\n"));
        }
        script.append(input.command()).append("\n");
        script.append("exit $?\n");
        return script.toString();
    }

    private List<Map<String, Object>> collectReports(AutomatedTestInput input, UUID testRunId, TaskExecutionContext context) {
        if (input.reportTargets() == null || input.reportTargets().isEmpty()) {
            return List.of();
        }
        List<Map<String, Object>> reports = new ArrayList<>();
        int index = 0;
        long totalBytes = 0;
        for (AutomatedTestReportTarget target : input.reportTargets()) {
            context.throwIfCancellationRequested();
            if (target.type() == AutomatedTestReportTargetType.FILE) {
                totalBytes += collectFile(input, testRunId, context, reports, target.path(), index++, totalBytes);
                continue;
            }
            for (String path : listDirectoryFiles(input, target.path(), context)) {
                totalBytes += collectFile(input, testRunId, context, reports, path, index++, totalBytes);
            }
        }
        return reports;
    }

    private List<String> listDirectoryFiles(AutomatedTestInput input, String directory, TaskExecutionContext context) {
        String command = workdirPrefix(input.workingDirectory())
                + "if [ -d " + shellQuote(directory) + " ]; then find " + shellQuote(directory)
                + " -maxdepth " + REPORT_DIRECTORY_MAX_DEPTH
                + " -type f -size -" + REPORT_FILE_MAX_BYTES + "c | head -n " + REPORT_DIRECTORY_MAX_FILES + "; fi";
        SshCommandResult result = sshRuntimeService.executeRemote(environmentTaskInput(input), command, null, false, 60, context);
        if (result.exitCode() != 0 || result.stdout().isBlank()) {
            return List.of();
        }
        return result.stdout().lines()
                .map(String::trim)
                .filter(line -> !line.isBlank())
                .filter(line -> !line.startsWith("/") && !line.contains(".."))
                .toList();
    }

    private long collectFile(
            AutomatedTestInput input,
            UUID testRunId,
            TaskExecutionContext context,
            List<Map<String, Object>> reports,
            String path,
            int index,
            long currentTotalBytes
    ) {
        String command = workdirPrefix(input.workingDirectory())
                + "if [ -f " + shellQuote(path) + " ]; then size=$(wc -c < " + shellQuote(path) + "); "
                + "if [ \"$size\" -le " + REPORT_FILE_MAX_BYTES + " ]; then printf 'RVPORT_REPORT_SIZE=%s\\n' \"$size\"; base64 " + shellQuote(path)
                + "; else printf 'RVPORT_REPORT_TOO_LARGE=%s\\n' \"$size\"; exit 0; fi; fi";
        SshCommandResult result = sshRuntimeService.executeRemote(environmentTaskInput(input), command, null, false, 120, context);
        if (result.exitCode() != 0 || result.stdout().isBlank() || result.stdout().startsWith("RVPORT_REPORT_TOO_LARGE=")) {
            reports.add(reportSummary(path, null, "SKIPPED", "报告文件不存在或超过大小限制", 0));
            return 0;
        }
        String base64 = result.stdout().lines()
                .filter(line -> !line.startsWith("RVPORT_REPORT_SIZE="))
                .reduce("", (left, right) -> left + right);
        byte[] content;
        try {
            content = Base64.getDecoder().decode(base64);
        } catch (IllegalArgumentException ex) {
            reports.add(reportSummary(path, null, "FAILED", "报告文件 Base64 解码失败", 0));
            return 0;
        }
        if (currentTotalBytes + content.length > REPORT_TOTAL_MAX_BYTES) {
            reports.add(reportSummary(path, null, "SKIPPED", "报告总大小超过限制", content.length));
            return 0;
        }
        String artifactType = "TEST_REPORT_" + index;
        var artifact = storedArtifactService.store(new cn.rvport.backend.artifact.StoredArtifactCreateCommand(
                input.projectId(),
                context.task().id(),
                StoredArtifactOwnerType.AUTOMATED_TEST,
                testRunId,
                artifactType,
                contentType(path),
                content,
                Map.of("remotePath", path, "collectedAt", OffsetDateTime.now().toString()),
                extension(path)
        ), context);
        reports.add(reportSummary(path, artifact.id(), "COLLECTED", null, content.length));
        return content.length;
    }

    private Map<String, Object> reportSummary(String path, UUID artifactId, String status, String message, long sizeBytes) {
        Map<String, Object> value = new LinkedHashMap<>();
        value.put("path", path);
        value.put("artifactId", artifactId);
        value.put("status", status);
        value.put("message", message);
        value.put("sizeBytes", sizeBytes);
        return value;
    }

    private void finishFailed(UUID testRunId, SshCommandResult result, List<Map<String, Object>> reports, TaskExecutionContext context, String message) {
        finishWithStatus(testRunId, TaskStatus.FAILED, result, reports, context, message);
    }

    private void finishWithStatus(UUID testRunId, TaskStatus status, SshCommandResult result, List<Map<String, Object>> reports, TaskExecutionContext context, String message) {
        context.publish(() -> {
        repository.finish(
                testRunId,
                status,
                result == null ? null : result.exitCode(),
                latestLogId(context.task().id(), TaskLogType.STDOUT),
                latestLogId(context.task().id(), TaskLogType.STDERR),
                latestLogId(context.task().id(), TaskLogType.COMBINED),
                message,
                reports == null ? List.of() : reports
        );
        testComparisonService.onAutomatedTestFinished(testRunId);
        return null;
        });
    }

    private boolean timeout(SshRuntimeException ex) {
        String text = (ex.getMessage() + " " + (ex.getCause() == null ? "" : ex.getCause().getMessage())).toLowerCase();
        return text.contains("超时") || text.contains("timeout");
    }

    private UUID latestLogId(UUID taskId, TaskLogType type) {
        return taskLogRepository.list(taskId, type, 1, 1).stream().findFirst().map(TaskLogResponse::id).orElse(null);
    }

    private String outputSummary(SshCommandResult result, List<Map<String, Object>> reports) {
        return "exitCode=%d, durationMs=%d, reportArtifacts=%d".formatted(
                result.exitCode(),
                result.duration().toMillis(),
                reports == null ? 0 : reports.size()
        );
    }

    private Map<String, Object> archiveSummary(AutomatedTestRunView run, SshCommandResult result, List<Map<String, Object>> reports) {
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("sourceRevisionId", run.sourceRevisionId());
        summary.put("environmentId", run.environmentId());
        summary.put("testBatchId", run.testBatchId());
        summary.put("testBatchRole", run.testBatchRole() == null ? null : run.testBatchRole().name());
        summary.put("status", run.status().name());
        summary.put("exitCode", result.exitCode());
        summary.put("durationMs", result.duration().toMillis());
        summary.put("reportArtifactCount", reports == null ? 0 : reports.stream().filter(this::collected).count());
        return summary;
    }

    private List<StoredArtifactView> collectedArtifacts(List<Map<String, Object>> reports) {
        if (reports == null || reports.isEmpty()) {
            return List.of();
        }
        return reports.stream()
                .filter(this::collected)
                .map(report -> UUID.fromString(String.valueOf(report.get("artifactId"))))
                .map(storedArtifactRepository::findById)
                .flatMap(java.util.Optional::stream)
                .toList();
    }

    private boolean collected(Map<String, Object> report) {
        return report != null && "COLLECTED".equals(report.get("status")) && report.get("artifactId") != null;
    }

    private String workdirPrefix(String workingDirectory) {
        return workingDirectory == null || workingDirectory.isBlank()
                ? ""
                : "cd " + shellQuote(workingDirectory) + " || exit 123; ";
    }

    private String contentType(String path) {
        String lower = path.toLowerCase();
        if (lower.endsWith(".json")) {
            return "application/json";
        }
        if (lower.endsWith(".html") || lower.endsWith(".htm")) {
            return "text/html";
        }
        return "text/plain";
    }

    private String extension(String path) {
        int index = path.lastIndexOf('.');
        if (index < 0 || index == path.length() - 1) {
            return "txt";
        }
        return path.substring(index + 1).replaceAll("[^A-Za-z0-9]", "");
    }

    private String shellQuote(String value) {
        return "'" + value.replace("'", "'\"'\"'") + "'";
    }
}
