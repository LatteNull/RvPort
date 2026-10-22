package cn.rvport.backend.worker;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.task.TaskErrorCode;
import cn.rvport.backend.task.TaskEventService;
import cn.rvport.backend.task.TaskEventType;
import cn.rvport.backend.task.TaskExecutionException;
import cn.rvport.backend.task.TaskLogResponse;
import cn.rvport.backend.task.TaskLogEventService;
import cn.rvport.backend.task.TaskLogService;
import cn.rvport.backend.task.TaskLogType;
import cn.rvport.backend.task.TaskRepository;
import cn.rvport.backend.task.TaskRuntimeHandleRepository;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.task.TaskView;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.OffsetDateTime;
import java.time.Duration;
import java.util.Optional;
import java.util.UUID;
import org.jooq.JSONB;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class DefaultTaskExecutionContextTests {
    @Test
    void rejectedAttemptCannotAppendLogsOrProgress() {
        TaskView task = task(TaskStatus.RUNNING, 0, "test");
        var handles = org.mockito.Mockito.mock(TaskRuntimeHandleRepository.class);
        var attempts = org.mockito.Mockito.mock(TaskAttemptService.class);
        var handle = new RunningTaskHandle(task.id(), UUID.randomUUID(), Thread.currentThread(), handles);
        var context = new DefaultTaskExecutionContext(task, JSONB.valueOf("{}"), taskRepository,
                taskEventService, taskLogService, new ObjectMapper(), handle, null).withAttemptService(attempts);
        when(attempts.publish(org.mockito.ArgumentMatchers.eq(task.id()), org.mockito.ArgumentMatchers.eq(handle.runtimeHandleId()),
                org.mockito.ArgumentMatchers.any())).thenThrow(new TaskAttemptLostException());
        assertThatThrownBy(() -> context.log(TaskLogType.STDOUT, "late")).isInstanceOf(TaskAttemptLostException.class);
        assertThatThrownBy(() -> context.progress(80, "late")).isInstanceOf(TaskAttemptLostException.class);
        assertThatThrownBy(() -> context.registerRemoteProcess(UUID.randomUUID(), 1L, 1L, "late"))
                .isInstanceOf(TaskAttemptLostException.class);
        CancellableResource resource = org.mockito.Mockito.mock(CancellableResource.class);
        assertThatThrownBy(() -> context.registerCancellableResource(resource)).isInstanceOf(TaskAttemptLostException.class);
        verify(resource).cancel();
        Process process = org.mockito.Mockito.mock(Process.class);
        ProcessHandle processHandle = org.mockito.Mockito.mock(ProcessHandle.class);
        when(process.toHandle()).thenReturn(processHandle);
        when(processHandle.descendants()).thenAnswer(call -> java.util.stream.Stream.empty());
        assertThatThrownBy(() -> context.registerLocalProcess(process, Duration.ZERO)).isInstanceOf(TaskAttemptLostException.class);
        verify(processHandle).destroy();
        org.mockito.Mockito.verifyNoInteractions(handles);
        org.mockito.Mockito.verifyNoInteractions(taskRepository, taskLogService, taskEventService);
    }

    @Mock
    private TaskRepository taskRepository;

    @Mock
    private TaskEventService taskEventService;

    @Mock
    private TaskLogService taskLogService;

    @Mock
    private TaskLogEventService taskLogEventService;

    @Test
    void parsesInputUpdatesProgressAndWritesLogEvent() {
        TaskView task = task(TaskStatus.RUNNING, 0, "开始");
        TaskView updated = new TaskView(
                task.id(),
                task.projectId(),
                task.type(),
                TaskStatus.RUNNING,
                35,
                "正在处理",
                task.createdBy(),
                task.createdAt(),
                task.queuedAt(),
                task.startedAt(),
                task.finishedAt(),
                task.timeoutSeconds(),
                task.errorCode(),
                task.errorMessage(),
                task.retryCount()
        );
        TaskLogResponse log = new TaskLogResponse(UUID.randomUUID(), task.id(), task.projectId(), TaskLogType.STDOUT,
                5L, 1L, "sha", "hello", OffsetDateTime.now());
        DefaultTaskExecutionContext context = contextWithLogEvents(task, JSONB.valueOf("{\"name\":\"demo\"}"));
        when(taskRepository.updateProgress(task.id(), 35, "正在处理")).thenReturn(updated);
        when(taskLogService.append(task.projectId(), task.id(), TaskLogType.STDOUT, "hello")).thenReturn(Optional.of(log));

        SampleInput input = context.input(SampleInput.class);
        context.progress(35, "正在处理");
        Optional<TaskLogResponse> response = context.log(TaskLogType.STDOUT, "hello");

        assertThat(input.name()).isEqualTo("demo");
        assertThat(context.task().progress()).isEqualTo(35);
        assertThat(response).contains(log);
        verify(taskEventService).append(task.projectId(), task.id(), TaskEventType.PROGRESS, TaskStatus.RUNNING, 35, "正在处理");
        verify(taskEventService).append(task.projectId(), task.id(), TaskEventType.LOG, TaskStatus.RUNNING, 35,
                "任务日志已更新", "INFO", "hello");
        verify(taskLogEventService).append(task.projectId(), task.id(), TaskLogType.STDOUT, "hello");
    }

    @Test
    void rejectsInvalidInputSnapshotAndIllegalProgress() {
        DefaultTaskExecutionContext invalidInput = context(task(TaskStatus.RUNNING, 0, "开始"), JSONB.valueOf("{bad"));

        assertThatThrownBy(() -> invalidInput.input(SampleInput.class))
                .isInstanceOf(TaskExecutionException.class)
                .extracting("errorCode")
                .isEqualTo(TaskErrorCode.INPUT_INVALID);

        DefaultTaskExecutionContext context = context(task(TaskStatus.RUNNING, 0, "开始"), JSONB.valueOf("{}"));
        assertThatThrownBy(() -> context.progress(101, "越界"))
                .isInstanceOf(TaskExecutionException.class)
                .extracting("errorCode")
                .isEqualTo(TaskErrorCode.PROGRESS_INVALID);
    }

    @Test
    void skipsLogEventWhenLogContentIsEmpty() {
        TaskView task = task(TaskStatus.RUNNING, 0, "开始");
        DefaultTaskExecutionContext context = context(task, JSONB.valueOf("{}"));
        when(taskLogService.append(task.projectId(), task.id(), TaskLogType.TOOL, "")).thenReturn(Optional.empty());

        Optional<TaskLogResponse> response = context.log(TaskLogType.TOOL, "");

        assertThat(response).isEmpty();
    }

    @Test
    void throwsCancellationExceptionWhenRunningHandleIsCancelled() {
        TaskRuntimeHandleRepository repository = org.mockito.Mockito.mock(TaskRuntimeHandleRepository.class);
        RunningTaskHandle handle = new RunningTaskHandle(UUID.randomUUID(), UUID.randomUUID(), Thread.currentThread(), repository);
        DefaultTaskExecutionContext context = new DefaultTaskExecutionContext(
                task(TaskStatus.RUNNING, 0, "开始"),
                JSONB.valueOf("{}"),
                taskRepository,
                taskEventService,
                taskLogService,
                new ObjectMapper(),
                handle,
                java.time.Duration.ofMillis(1));

        try {
            handle.requestCancel();

            assertThat(context.isCancellationRequested()).isTrue();
            assertThatThrownBy(context::throwIfCancellationRequested)
                    .isInstanceOf(TaskCancelledException.class);
        } finally {
            Thread.interrupted();
        }
    }

    @Test
    void acceptsBoundaryProgressAndIgnoresDeletedTaskUpdate() {
        TaskView task = task(TaskStatus.RUNNING, 10, "running");
        DefaultTaskExecutionContext context = context(task, JSONB.valueOf("{}"));
        when(taskRepository.updateProgress(task.id(), 0, null)).thenReturn(null);

        context.progress(0, null);

        assertThat(context.task()).isSameAs(task);
        assertThatThrownBy(() -> context.progress(-1, "invalid"))
                .isInstanceOf(TaskExecutionException.class)
                .extracting("errorCode").isEqualTo(TaskErrorCode.PROGRESS_INVALID);
    }

    @Test
    void routesStderrAsWarningAndDoesNotPublishToolLogStreamEvent() {
        TaskView task = task(TaskStatus.RUNNING, 20, "running");
        TaskLogResponse stderr = new TaskLogResponse(UUID.randomUUID(), task.id(), task.projectId(), TaskLogType.STDERR,
                4L, 1L, "sha", "failure", OffsetDateTime.now());
        DefaultTaskExecutionContext context = contextWithLogEvents(task, JSONB.valueOf("{}"));
        when(taskLogService.append(task.projectId(), task.id(), TaskLogType.STDERR, "failure")).thenReturn(Optional.of(stderr));
        when(taskLogService.append(task.projectId(), task.id(), TaskLogType.TOOL, "tool")).thenReturn(Optional.empty());

        context.log(TaskLogType.STDERR, "failure");
        context.log(TaskLogType.TOOL, "tool");

        verify(taskLogEventService).append(task.projectId(), task.id(), TaskLogType.STDERR, "failure");
        verify(taskEventService).append(task.projectId(), task.id(), TaskEventType.LOG, TaskStatus.RUNNING, 20,
                "任务日志已更新", "WARN", "failure");
        org.mockito.Mockito.verifyNoMoreInteractions(taskLogEventService);
    }

    @Test
    void observesThreadInterruptionWithoutRuntimeHandle() {
        DefaultTaskExecutionContext context = context(task(TaskStatus.RUNNING, 0, "running"), JSONB.valueOf("{}"));
        Thread.currentThread().interrupt();
        try {
            assertThat(context.isCancellationRequested()).isTrue();
            assertThatThrownBy(context::throwIfCancellationRequested).isInstanceOf(TaskCancelledException.class);
        } finally {
            Thread.interrupted();
        }
    }

    @Test
    void registersOnlyNonNullResourcesWhenRuntimeHandleExists() {
        TaskView task = task(TaskStatus.RUNNING, 0, "running");
        RunningTaskHandle handle = org.mockito.Mockito.mock(RunningTaskHandle.class);
        DefaultTaskExecutionContext context = new DefaultTaskExecutionContext(task, JSONB.valueOf("{}"), taskRepository,
                taskEventService, taskLogService, new ObjectMapper(), handle, Duration.ofSeconds(7));
        Process process = org.mockito.Mockito.mock(Process.class);
        CancellableResource resource = org.mockito.Mockito.mock(CancellableResource.class);
        UUID environmentId = UUID.randomUUID();

        context.registerLocalProcess(null, null);
        context.registerLocalProcess(process, null);
        context.registerLocalProcess(process, Duration.ofSeconds(2));
        context.registerCancellableResource(null);
        context.registerCancellableResource(resource);
        context.registerRemoteProcess(environmentId, 1L, 2L, "marker");

        verify(handle).registerLocalProcess(process, Duration.ofSeconds(7));
        verify(handle).registerLocalProcess(process, Duration.ofSeconds(2));
        verify(handle).addResource(resource);
        verify(handle).registerRemoteProcess(environmentId, 1L, 2L, "marker");
    }

    @Test
    void ignoresResourceRegistrationWithoutRuntimeHandle() {
        DefaultTaskExecutionContext context = context(task(TaskStatus.RUNNING, 0, "running"), JSONB.valueOf("{}"));
        context.registerLocalProcess(org.mockito.Mockito.mock(Process.class), Duration.ZERO);
        context.registerCancellableResource(org.mockito.Mockito.mock(CancellableResource.class));
        context.registerRemoteProcess(UUID.randomUUID(), null, null, null);
        assertThat(context.isCancellationRequested()).isFalse();
    }

    private DefaultTaskExecutionContext context(TaskView task, JSONB inputSnapshot) {
        return new DefaultTaskExecutionContext(task, inputSnapshot, taskRepository, taskEventService, taskLogService, new ObjectMapper());
    }

    private DefaultTaskExecutionContext contextWithLogEvents(TaskView task, JSONB inputSnapshot) {
        return new DefaultTaskExecutionContext(
                task,
                inputSnapshot,
                taskRepository,
                taskEventService,
                taskLogService,
                taskLogEventService,
                new ObjectMapper(),
                null,
                null
        );
    }

    private TaskView task(TaskStatus status, int progress, String message) {
        return new TaskView(
                UUID.randomUUID(),
                UUID.randomUUID(),
                "KB_SCAN",
                status,
                progress,
                message,
                UUID.randomUUID(),
                OffsetDateTime.now(),
                OffsetDateTime.now(),
                OffsetDateTime.now(),
                null,
                300,
                null,
                null,
                0
        );
    }

    private record SampleInput(String name) {
    }
}
