package cn.rvport.backend.dependency.autofix;

import cn.rvport.backend.dependency.DependencyAnalysisCreateRequest;
import cn.rvport.backend.dependency.DependencyAnalysisCreateResponse;
import cn.rvport.backend.dependency.DependencyAnalysisService;
import cn.rvport.backend.environment.runtime.EnvironmentTaskInput;
import cn.rvport.backend.environment.runtime.SshCommandResult;
import cn.rvport.backend.environment.runtime.SshRuntimeException;
import cn.rvport.backend.environment.runtime.SshRuntimeService;
import cn.rvport.backend.task.RvPortTaskTypes;
import cn.rvport.backend.task.TaskErrorCode;
import cn.rvport.backend.task.TaskExecutionException;
import cn.rvport.backend.task.TaskLogType;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.task.ToolRunRepository;
import cn.rvport.backend.worker.TaskCancelledException;
import cn.rvport.backend.worker.TaskAttemptLostException;
import cn.rvport.backend.worker.TaskExecutionContext;
import cn.rvport.backend.worker.TaskHandler;
import cn.rvport.backend.worker.TaskHandlerResult;
import java.time.OffsetDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Component;

@Component
public class DependencyAutoFixHandler implements TaskHandler {

    private static final String TOOL_NAME = "rvport-dependency-auto-fix";
    private static final String TOOL_VERSION = "1";
    private static final int INSTALL_TIMEOUT_SECONDS = 1800;

    private final DependencyAutoFixRepository repository;
    private final SshRuntimeService sshRuntimeService;
    private final DependencyPackageInstallPlanner installPlanner;
    private final DependencyAnalysisService dependencyAnalysisService;
    private final ToolRunRepository toolRunRepository;

    public DependencyAutoFixHandler(
            DependencyAutoFixRepository repository,
            SshRuntimeService sshRuntimeService,
            DependencyPackageInstallPlanner installPlanner,
            DependencyAnalysisService dependencyAnalysisService,
            ToolRunRepository toolRunRepository
    ) {
        this.repository = repository;
        this.sshRuntimeService = sshRuntimeService;
        this.installPlanner = installPlanner;
        this.dependencyAnalysisService = dependencyAnalysisService;
        this.toolRunRepository = toolRunRepository;
    }

    @Override
    public String taskType() {
        return RvPortTaskTypes.DEPENDENCY_AUTO_FIX;
    }

    @Override
    public TaskHandlerResult handle(TaskExecutionContext context) {
        DependencyAutoFixTaskInput input = context.input(DependencyAutoFixTaskInput.class);
        DependencyAutoFixRunView run = repository.findRun(input.autoFixRunId())
                .orElseThrow(() -> new TaskExecutionException(TaskErrorCode.RESOURCE_NOT_FOUND, "依赖自动修复运行不存在", null));
        UUID toolRunId = context.publish(() -> toolRunRepository.create(
                context.task().projectId(),
                context.task().id(),
                TOOL_NAME,
                TOOL_VERSION,
                "依赖自动修复",
                TaskStatus.RUNNING,
                OffsetDateTime.now()
        ));
        try {
            context.publish(() -> { repository.markRunRunning(run.id()); return null; });
            context.progress(10, "开始依赖自动修复");
            List<DependencyAutoFixItemView> items = repository.listPendingItems(run.id());
            int index = 0;
            for (DependencyAutoFixItemView item : items) {
                context.throwIfCancellationRequested();
                index++;
                int progress = 10 + Math.min(70, (int) Math.round(index * 70.0 / Math.max(1, items.size())));
                context.progress(progress, "安装依赖包 " + item.installPackageName());
                processItem(context, input, item);
            }
            Map<String, Object> summary = summary(run.id());
            boolean hasSatisfied = positiveCount(summary) > 0;
            if (hasSatisfied && input.shouldRerunDependencyAnalysis()) {
                context.progress(85, "创建修复后依赖分析任务");
                try {
                    context.publish(() -> {
                    DependencyAnalysisCreateResponse rerun = dependencyAnalysisService.create(
                            run.projectId(),
                            new DependencyAnalysisCreateRequest(run.sourceRevisionId()),
                            context.task().createdBy(),
                            false,
                            null
                    );
                    summary.put("rerunDependencyAnalysisRunId", rerun.analysisRunId());
                    summary.put("rerunDependencyAnalysisTaskId", rerun.taskId());
                    repository.linkRerun(run.id(), rerun.analysisRunId(), rerun.taskId(), summary, finalStatus(summary));
                    return null;
                    });
                } catch (TaskAttemptLostException ex) {
                    throw ex;
                } catch (RuntimeException ex) {
                    summary.put("rerunError", safeMessage(ex.getMessage()));
                    context.publish(() -> {
                    repository.markRunFinished(run.id(), DependencyAutoFixRunStatus.SUCCEEDED_WITH_REANALYSIS_FAILED,
                            summary, "依赖安装完成，但重新创建依赖分析失败");
                    toolRunRepository.finish(toolRunId, TaskStatus.SUCCEEDED, 0, summary);
                    return null;
                    });
                    context.progress(90, "依赖安装完成，重新分析创建失败");
                    return TaskHandlerResult.success("依赖自动修复完成，重新分析创建失败");
                }
            } else {
                context.publish(() -> {
                repository.markRunFinished(run.id(), finalStatus(summary), summary,
                        hasSatisfied ? null : "没有依赖包安装成功或满足");
                return null;
                });
            }
            if (!hasSatisfied) {
                throw new TaskExecutionException(TaskErrorCode.REMOTE_COMMAND_FAILED, "依赖自动修复未安装任何软件包", null);
            }
            context.publish(() -> { toolRunRepository.finish(toolRunId, TaskStatus.SUCCEEDED, 0, summary); return null; });
            context.progress(90, "依赖自动修复完成");
            return TaskHandlerResult.success("依赖自动修复完成");
        } catch (TaskAttemptLostException ex) {
            throw ex;
        } catch (TaskCancelledException ex) {
            context.publish(() -> {
            repository.cancelPendingItems(run.id());
            repository.markRunFinished(run.id(), DependencyAutoFixRunStatus.CANCELLED, Map.of("error", "任务已取消"), "任务已取消");
            toolRunRepository.finish(toolRunId, TaskStatus.CANCELLED, null, Map.of("error", "任务已取消"));
            return null;
            });
            throw ex;
        } catch (TaskExecutionException ex) {
            context.publish(() -> {
            toolRunRepository.finish(toolRunId, TaskStatus.FAILED, null, Map.of("error", ex.safeMessage(), "errorCode", ex.errorCode()));
            return null;
            });
            throw ex;
        } catch (RuntimeException ex) {
            context.publish(() -> {
            repository.markRunFinished(run.id(), DependencyAutoFixRunStatus.FAILED,
                    Map.of("error", "依赖自动修复失败"), "依赖自动修复失败");
            toolRunRepository.finish(toolRunId, TaskStatus.FAILED, null, Map.of("error", "依赖自动修复失败"));
            return null;
            });
            throw new TaskExecutionException(TaskErrorCode.HANDLER_FAILED, "依赖自动修复失败", ex);
        }
    }

    private void processItem(TaskExecutionContext context, DependencyAutoFixTaskInput input, DependencyAutoFixItemView item) {
        context.publish(() -> { repository.markItemRunning(item.id()); return null; });
        try {
            String script = installPlanner.rpmInstallScript(item);
            SshCommandResult result = sshRuntimeService.executeRemote(
                    new EnvironmentTaskInput(input.projectId(), input.targetEnvironmentId(), null, INSTALL_TIMEOUT_SECONDS),
                    script,
                    null,
                    false,
                    INSTALL_TIMEOUT_SECONDS,
                    context
            );
            context.log(TaskLogType.STDOUT, result.stdout());
            context.log(TaskLogType.STDERR, result.stderr());
            DependencyAutoFixItemStatus status = status(result);
            String error = status == DependencyAutoFixItemStatus.FAILED || status == DependencyAutoFixItemStatus.SKIPPED_UNAVAILABLE
                    ? safeMessage(firstNonBlank(result.stderr(), result.stdout()))
                    : null;
            context.publish(() -> {
            repository.markItemFinished(item.id(), status, result.exitCode(), error, Map.of(
                    "durationMs", result.duration().toMillis(),
                    "exitCode", result.exitCode(),
                    "installPackageName", item.installPackageName(),
                    "installVersionConstraint", item.installVersionConstraint() == null ? "" : item.installVersionConstraint()
            ));
            return null;
            });
        } catch (IllegalArgumentException ex) {
            context.publish(() -> {
            repository.markItemFinished(item.id(), DependencyAutoFixItemStatus.FAILED, null, ex.getMessage(), Map.of("validation", "package-name-or-version"));
            return null;
            });
        } catch (SshRuntimeException ex) {
            context.publish(() -> {
            repository.markItemFinished(item.id(), DependencyAutoFixItemStatus.FAILED, null, "依赖安装 SSH 执行失败", Map.of("sshError", safeMessage(ex.getMessage())));
            return null;
            });
        }
    }

    private DependencyAutoFixItemStatus status(SshCommandResult result) {
        if (result.exitCode() == 0) {
            return DependencyAutoFixItemStatus.SUCCEEDED;
        }
        String output = (result.stdout() == null ? "" : result.stdout()) + "\n" + (result.stderr() == null ? "" : result.stderr());
        if (result.exitCode() == 10 || output.contains("RVPORT_AUTO_FIX_ALREADY_SATISFIED")) {
            return DependencyAutoFixItemStatus.SKIPPED_ALREADY_SATISFIED;
        }
        if (result.exitCode() == 11 || output.contains("RVPORT_AUTO_FIX_PACKAGE_UNAVAILABLE") || output.contains("RVPORT_AUTO_FIX_MAJOR_UNAVAILABLE")) {
            return DependencyAutoFixItemStatus.SKIPPED_UNAVAILABLE;
        }
        return DependencyAutoFixItemStatus.FAILED;
    }

    private Map<String, Object> summary(UUID runId) {
        return new LinkedHashMap<>(repository.summaryCounts(runId));
    }

    private DependencyAutoFixRunStatus finalStatus(Map<String, Object> summary) {
        long failed = number(summary.get("failed"));
        long unavailable = number(summary.get("skippedUnavailable"));
        long positive = positiveCount(summary);
        if (positive == 0) {
            return DependencyAutoFixRunStatus.FAILED;
        }
        if (failed > 0 || unavailable > 0) {
            return DependencyAutoFixRunStatus.PARTIALLY_SUCCEEDED;
        }
        return DependencyAutoFixRunStatus.SUCCEEDED;
    }

    private long positiveCount(Map<String, Object> summary) {
        return number(summary.get("succeeded")) + number(summary.get("alreadySatisfied"));
    }

    private long number(Object value) {
        return value instanceof Number number ? number.longValue() : 0L;
    }

    private String firstNonBlank(String first, String second) {
        return first != null && !first.isBlank() ? first : second == null ? "" : second;
    }

    private String safeMessage(String value) {
        if (value == null || value.isBlank()) {
            return "";
        }
        String text = value.replace('\r', ' ').replace('\n', ' ')
                .replaceAll("(?i)(password|token|privateKey|private_key|passphrase|secret)(\\s*[=:]\\s*)\\S+", "$1$2****");
        return text.length() > 500 ? text.substring(0, 500) : text;
    }
}
