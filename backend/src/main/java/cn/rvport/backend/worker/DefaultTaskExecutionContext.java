package cn.rvport.backend.worker;

import cn.rvport.backend.task.TaskErrorCode;
import cn.rvport.backend.task.TaskEventService;
import cn.rvport.backend.task.TaskEventType;
import cn.rvport.backend.task.TaskExecutionException;
import cn.rvport.backend.task.TaskLogResponse;
import cn.rvport.backend.task.TaskLogEventService;
import cn.rvport.backend.task.TaskLogService;
import cn.rvport.backend.task.TaskLogType;
import cn.rvport.backend.task.TaskRepository;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.task.TaskView;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Duration;
import java.util.Optional;
import java.util.UUID;
import org.jooq.JSONB;

public class DefaultTaskExecutionContext implements TaskExecutionContext {

    private final TaskRepository taskRepository;
    private final TaskEventService taskEventService;
    private final TaskLogService taskLogService;
    private final TaskLogEventService taskLogEventService;
    private final ObjectMapper objectMapper;
    private final JSONB inputSnapshot;
    private final RunningTaskHandle runningTaskHandle;
    private final Duration cancelGracePeriod;
    private TaskView task;
    private TaskAttemptService attempts;

    public DefaultTaskExecutionContext withAttemptService(TaskAttemptService attempts) {
        this.attempts = java.util.Objects.requireNonNull(attempts);
        java.util.Objects.requireNonNull(runningTaskHandle);
        return this;
    }

    @Override
    public <T> T publish(java.util.function.Supplier<T> operation) {
        return attempts == null ? operation.get()
                : attempts.publish(task.id(), runningTaskHandle.runtimeHandleId(), operation);
    }

    public DefaultTaskExecutionContext(
            TaskView task,
            JSONB inputSnapshot,
            TaskRepository taskRepository,
            TaskEventService taskEventService,
            TaskLogService taskLogService,
            ObjectMapper objectMapper
    ) {
        this(task, inputSnapshot, taskRepository, taskEventService, taskLogService, null, objectMapper, null, null);
    }

    public DefaultTaskExecutionContext(
            TaskView task,
            JSONB inputSnapshot,
            TaskRepository taskRepository,
            TaskEventService taskEventService,
            TaskLogService taskLogService,
            ObjectMapper objectMapper,
            RunningTaskHandle runningTaskHandle,
            Duration cancelGracePeriod
    ) {
        this(task, inputSnapshot, taskRepository, taskEventService, taskLogService, null, objectMapper, runningTaskHandle, cancelGracePeriod);
    }

    public DefaultTaskExecutionContext(
            TaskView task,
            JSONB inputSnapshot,
            TaskRepository taskRepository,
            TaskEventService taskEventService,
            TaskLogService taskLogService,
            TaskLogEventService taskLogEventService,
            ObjectMapper objectMapper,
            RunningTaskHandle runningTaskHandle,
            Duration cancelGracePeriod
    ) {
        this.task = task;
        this.inputSnapshot = inputSnapshot;
        this.taskRepository = taskRepository;
        this.taskEventService = taskEventService;
        this.taskLogService = taskLogService;
        this.taskLogEventService = taskLogEventService;
        this.objectMapper = objectMapper;
        this.runningTaskHandle = runningTaskHandle;
        this.cancelGracePeriod = cancelGracePeriod == null ? Duration.ofSeconds(5) : cancelGracePeriod;
    }

    @Override
    public TaskView task() {
        return task;
    }

    @Override
    public <T> T input(Class<T> inputType) {
        throwIfCancellationRequested();
        try {
            return objectMapper.readValue(inputSnapshot.data(), inputType);
        } catch (JsonProcessingException ex) {
            throw new TaskExecutionException(TaskErrorCode.INPUT_INVALID, "任务输入快照无法解析", ex);
        }
    }

    @Override
    public void progress(int progress, String message) {
        throwIfCancellationRequested();
        if (progress < 0 || progress > 100) {
            throw new TaskExecutionException(TaskErrorCode.PROGRESS_INVALID, "任务进度值非法", null);
        }
        publish(() -> {
        TaskView updated = taskRepository.updateProgress(task.id(), progress, message);
        if (updated != null) {
            task = updated;
            taskEventService.append(
                    updated.projectId(),
                    updated.id(),
                    TaskEventType.PROGRESS,
                    TaskStatus.RUNNING,
                    updated.progress(),
                    updated.message()
            );
        }
        return null;
        });
    }

    @Override
    public Optional<TaskLogResponse> log(TaskLogType logType, String content) {
        throwIfCancellationRequested();
        return publish(() -> {
        Optional<TaskLogResponse> log = taskLogService.append(task.projectId(), task.id(), logType, content);
        if (taskLogEventService != null && (logType == TaskLogType.STDOUT || logType == TaskLogType.STDERR)) {
            taskLogEventService.append(task.projectId(), task.id(), logType, content);
        }
        log.ifPresent(item -> taskEventService.append(
                task.projectId(),
                task.id(),
                TaskEventType.LOG,
                task.status(),
                task.progress(),
                "任务日志已更新",
                eventLogLevel(logType),
                item.excerpt()
        ));
        return log;
        });
    }

    private String eventLogLevel(TaskLogType logType) {
        return logType == TaskLogType.STDERR ? "WARN" : "INFO";
    }

    @Override
    public boolean isCancellationRequested() {
        return (runningTaskHandle != null && runningTaskHandle.isCancellationRequested())
                || Thread.currentThread().isInterrupted();
    }

    @Override
    public void throwIfCancellationRequested() {
        if (runningTaskHandle != null) {
            runningTaskHandle.throwIfCancellationRequested();
            publish(() -> null);
            return;
        }
        TaskExecutionContext.super.throwIfCancellationRequested();
    }

    @Override
    public void registerLocalProcess(Process process, Duration gracePeriod) {
        if (process == null || runningTaskHandle == null) {
            return;
        }
        Duration grace = gracePeriod == null ? cancelGracePeriod : gracePeriod;
        try {
            publish(() -> null);
        } catch (TaskAttemptLostException ex) {
            new LocalProcessCancellableResource(process, grace).cancel();
            throw ex;
        }
        runningTaskHandle.registerLocalProcess(process, grace);
    }

    @Override
    public void registerCancellableResource(CancellableResource resource) {
        if (resource == null || runningTaskHandle == null) {
            return;
        }
        try {
            publish(() -> null);
        } catch (TaskAttemptLostException ex) {
            resource.cancel();
            throw ex;
        }
        runningTaskHandle.addResource(resource);
    }

    @Override
    public void registerRemoteProcess(UUID environmentId, Long remotePid, Long remotePgid, String commandMarker) {
        if (runningTaskHandle != null) {
            publish(() -> {
                runningTaskHandle.registerRemoteProcess(environmentId, remotePid, remotePgid, commandMarker);
                return null;
            });
        }
    }
}
