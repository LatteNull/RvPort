package cn.rvport.backend.worker;

import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.Mockito.doReturn;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.config.RvPortProperties;
import cn.rvport.backend.config.WorkerProperties;
import cn.rvport.backend.jooq.tables.records.TasksRecord;
import cn.rvport.backend.mail.MailConfig;
import cn.rvport.backend.mail.MailConfigService;
import cn.rvport.backend.mail.MailDeliveryService;
import cn.rvport.backend.task.TaskErrorCode;
import cn.rvport.backend.task.TaskEventService;
import cn.rvport.backend.task.TaskEventType;
import cn.rvport.backend.task.TaskExecutionException;
import cn.rvport.backend.task.TaskLogRepository;
import cn.rvport.backend.task.TaskLogService;
import cn.rvport.backend.task.TaskLogEventService;
import cn.rvport.backend.task.TaskLogSseBroker;
import cn.rvport.backend.task.TaskRepository;
import cn.rvport.backend.task.TaskRuntimeHandleRepository;
import cn.rvport.backend.task.TaskRuntimeHandleStatus;
import cn.rvport.backend.task.TaskRuntimeHandleType;
import cn.rvport.backend.task.TaskRuntimeHandleView;
import cn.rvport.backend.task.TaskSecretPayloadService;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.task.TaskView;
import cn.rvport.backend.user.UserRepository;
import cn.rvport.backend.user.UserStatus;
import cn.rvport.backend.user.UserView;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.Path;
import java.time.OffsetDateTime;
import java.util.Optional;
import java.util.UUID;
import org.jooq.JSONB;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;
import org.springframework.http.HttpStatus;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
@ExtendWith(OutputCaptureExtension.class)
class TaskWorkerServiceTests {

    @Mock
    private TaskRepository taskRepository;

    @Mock
    private TaskEventService taskEventService;

    @Mock
    private TaskHandlerRegistry taskHandlerRegistry;

    @Mock
    private TaskHandler taskHandler;

    @Mock
    private TaskLogRepository taskLogRepository;

    @Mock
    private MailDeliveryService mailDeliveryService;

    @Mock
    private MailConfigService mailConfigService;

    @Mock
    private UserRepository userRepository;

    @Mock
    private TaskRuntimeHandleRepository runtimeHandleRepository;

    @Mock
    private TaskLogEventService taskLogEventService;

    @Mock
    private TaskLogSseBroker taskLogSseBroker;

    @Mock
    private TaskSecretPayloadService taskSecretPayloadService;

    @Mock
    private TaskAttemptService attempts;

    @Test
    void skipsDuplicateOrTerminalMessageWhenTaskCannotBeClaimed() {
        TaskWorkerService service = service();
        UUID taskId = UUID.randomUUID();
        TasksRecord record = taskRecord(taskId, TaskStatus.SUCCEEDED);
        when(taskRepository.findRecordById(taskId)).thenReturn(Optional.of(record));
        when(taskRepository.claim(taskId, "任务开始执行")).thenReturn(null);

        service.process(taskId);

        verify(taskHandlerRegistry, never()).find(any());
    }

    @Test
    void marksTaskFailedWhenHandlerIsMissing() {
        TaskWorkerService service = service();
        UUID taskId = UUID.randomUUID();
        TaskView running = task(taskId, TaskStatus.RUNNING);
        TaskView failed = task(taskId, TaskStatus.FAILED);
        when(taskRepository.findRecordById(taskId)).thenReturn(Optional.of(taskRecord(taskId, TaskStatus.QUEUED)));
        when(taskRepository.claim(taskId, "任务开始执行")).thenReturn(running);
        when(taskHandlerRegistry.find("KB_SCAN")).thenReturn(Optional.empty());
        when(taskRepository.completeIfActive(taskId, TaskStatus.FAILED, "任务类型没有可用处理器", TaskErrorCode.HANDLER_NOT_FOUND, "任务类型没有可用处理器"))
                .thenReturn(failed);

        service.process(taskId);

        verify(taskEventService).append(running.projectId(), taskId, TaskEventType.STARTED, TaskStatus.RUNNING, running.progress(), running.message());
        verify(taskEventService).append(failed.projectId(), taskId, TaskEventType.FAILED, TaskStatus.FAILED, failed.progress(), failed.message());
    }

    @Test
    void lostOwnershipBeforeStartedDoesNotInvokeHandler() {
        TaskWorkerService service = service();
        UUID taskId = UUID.randomUUID();
        when(taskRepository.findRecordById(taskId)).thenReturn(Optional.of(taskRecord(taskId, TaskStatus.QUEUED)));
        when(taskRepository.claim(taskId, "任务开始执行")).thenReturn(task(taskId, TaskStatus.RUNNING));
        org.mockito.Mockito.doThrow(new TaskAttemptLostException()).when(attempts).publish(any(), any(), any());
        service.process(taskId);
        verifyNoInteractions(taskHandlerRegistry, taskEventService);
    }

    @Test
    void handlerCannotRetryAfterLosingAttempt() {
        TaskWorkerService service = service();
        UUID taskId = UUID.randomUUID();
        when(taskRepository.findRecordById(taskId)).thenReturn(Optional.of(taskRecord(taskId, TaskStatus.QUEUED)));
        when(taskRepository.claim(taskId, "任务开始执行")).thenReturn(task(taskId, TaskStatus.RUNNING));
        when(taskHandlerRegistry.find("KB_SCAN")).thenReturn(Optional.of(taskHandler));
        when(taskHandler.handle(any())).thenThrow(new TaskAttemptLostException());
        service.process(taskId, 1, 3);
        verify(taskRepository, never()).markRetry(any(), anyInt(), any(), any(), any());
        verify(taskRepository, never()).completeIfActive(any(), any(), any(), any(), any());
    }

    @Test
    void completesTaskAfterHandlerSuccess() {
        TaskWorkerService service = service();
        UUID taskId = UUID.randomUUID();
        TaskView running = task(taskId, TaskStatus.RUNNING);
        TaskView succeeded = task(taskId, TaskStatus.SUCCEEDED);
        TasksRecord record = taskRecord(taskId, TaskStatus.QUEUED);
        when(taskRepository.findRecordById(taskId)).thenReturn(Optional.of(record));
        when(taskRepository.claim(taskId, "任务开始执行")).thenReturn(running);
        when(taskHandlerRegistry.find("KB_SCAN")).thenReturn(Optional.of(taskHandler));
        when(taskHandler.handle(any(TaskExecutionContext.class))).thenReturn(TaskHandlerResult.success("完成"));
        when(taskRepository.completeIfActive(taskId, TaskStatus.SUCCEEDED, "完成", null, null)).thenReturn(succeeded);

        service.process(taskId);

        verify(taskHandler).handle(any(TaskExecutionContext.class));
        verify(taskEventService).append(succeeded.projectId(), taskId, TaskEventType.SUCCEEDED, TaskStatus.SUCCEEDED, succeeded.progress(), succeeded.message());
        verify(taskSecretPayloadService).deleteByTaskId(taskId);
        verify(taskLogSseBroker).publishTerminal(succeeded);
    }

    @Test
    void rejectsClaimWhenRuntimeHandleCannotBeCreated() {
        TaskWorkerService service = service();
        UUID taskId = UUID.randomUUID();
        TaskView running = task(taskId, TaskStatus.RUNNING);
        TasksRecord record = taskRecord(taskId, TaskStatus.QUEUED);
        when(taskRepository.findRecordById(taskId)).thenReturn(Optional.of(record));
        when(taskRepository.claim(taskId, "任务开始执行")).thenReturn(running);
        doReturn(null).when(runtimeHandleRepository).createTaskHandle(eq(running.id()), eq(running.projectId()), any());
        assertThrows(TaskAttemptLostException.class, () -> service.process(taskId));

        verify(taskHandler, never()).handle(any());
        verifyNoInteractions(taskSecretPayloadService, taskLogSseBroker);
    }

    @Test
    void skipsMissingTaskMessageWithoutLookingUpHandler() {
        TaskWorkerService service = service();
        UUID taskId = UUID.randomUUID();
        when(taskRepository.findRecordById(taskId)).thenReturn(Optional.empty());

        service.process(taskId);

        verify(taskRepository, never()).claim(any(), any());
        verify(taskHandlerRegistry, never()).find(any());
    }

    @Test
    void marksTaskFailedWhenHandlerThrows() {
        TaskWorkerService service = service();
        UUID taskId = UUID.randomUUID();
        TaskView running = task(taskId, TaskStatus.RUNNING);
        TaskView failed = task(taskId, TaskStatus.FAILED);
        TasksRecord record = taskRecord(taskId, TaskStatus.QUEUED);
        when(taskRepository.findRecordById(taskId)).thenReturn(Optional.of(record));
        when(taskRepository.claim(taskId, "任务开始执行")).thenReturn(running);
        when(taskHandlerRegistry.find("KB_SCAN")).thenReturn(Optional.of(taskHandler));
        when(taskHandler.handle(any(TaskExecutionContext.class))).thenThrow(new RuntimeException("boom"));
        when(taskRepository.completeIfActive(taskId, TaskStatus.FAILED, "boom", TaskErrorCode.HANDLER_FAILED, "boom")).thenReturn(failed);

        service.process(taskId);

        verify(taskEventService).append(failed.projectId(), taskId, TaskEventType.FAILED, TaskStatus.FAILED, failed.progress(), failed.message());
        verify(taskSecretPayloadService).deleteByTaskId(taskId);
    }

    @Test
    void requeuesTaskWhenHandlerThrowsBeforeMaxAttempts() {
        TaskWorkerService service = service();
        UUID taskId = UUID.randomUUID();
        TaskView running = task(taskId, TaskStatus.RUNNING);
        TaskView queued = task(taskId, TaskStatus.QUEUED);
        TasksRecord record = taskRecord(taskId, TaskStatus.QUEUED);
        when(taskRepository.findRecordById(taskId)).thenReturn(Optional.of(record));
        when(taskRepository.claim(taskId, "任务开始执行")).thenReturn(running);
        when(taskHandlerRegistry.find("KB_SCAN")).thenReturn(Optional.of(taskHandler));
        when(taskHandler.handle(any(TaskExecutionContext.class))).thenThrow(new RuntimeException("boom"));
        when(taskRepository.markRetry(
                taskId,
                1,
                "任务执行失败，等待第 2 次重试",
                TaskErrorCode.HANDLER_FAILED,
                "boom"
        )).thenReturn(queued);

        assertThrows(TaskRetryableException.class, () -> service.process(taskId, 1, 3));

        verify(taskRepository).markRetry(taskId, 1, "任务执行失败，等待第 2 次重试", TaskErrorCode.HANDLER_FAILED, "boom");
        verify(taskRepository, never()).completeIfActive(eq(taskId), eq(TaskStatus.FAILED), any(), any(), any());
        verify(taskEventService).append(queued.projectId(), taskId, TaskEventType.QUEUED, TaskStatus.QUEUED, queued.progress(), queued.message());
        verify(taskSecretPayloadService, never()).deleteByTaskId(taskId);
    }

    @Test
    void skipsRetryEventWhenTaskWasDeletedDuringRetryHandling() {
        TaskWorkerService service = service();
        UUID taskId = UUID.randomUUID();
        TaskView running = task(taskId, TaskStatus.RUNNING);
        TasksRecord record = taskRecord(taskId, TaskStatus.QUEUED);
        when(taskRepository.findRecordById(taskId)).thenReturn(Optional.of(record));
        when(taskRepository.claim(taskId, "任务开始执行")).thenReturn(running);
        when(taskHandlerRegistry.find("KB_SCAN")).thenReturn(Optional.of(taskHandler));
        when(taskHandler.handle(any(TaskExecutionContext.class))).thenThrow(new RuntimeException("boom"));
        when(taskRepository.markRetry(
                taskId,
                1,
                "任务执行失败，等待第 2 次重试",
                TaskErrorCode.HANDLER_FAILED,
                "boom"
        )).thenReturn(null);

        service.process(taskId, 1, 3);

        verify(taskEventService, never()).append(eq(running.projectId()), eq(taskId), eq(TaskEventType.QUEUED), any(), anyInt(), any());
        verify(taskRepository, never()).completeIfActive(eq(taskId), eq(TaskStatus.FAILED), any(), any(), any());
    }

    @Test
    void skipsFailureEventWhenTaskWasDeletedDuringFailureHandling() {
        TaskWorkerService service = service();
        UUID taskId = UUID.randomUUID();
        TaskView running = task(taskId, TaskStatus.RUNNING);
        TasksRecord record = taskRecord(taskId, TaskStatus.QUEUED);
        when(taskRepository.findRecordById(taskId)).thenReturn(Optional.of(record));
        when(taskRepository.claim(taskId, "任务开始执行")).thenReturn(running);
        when(taskHandlerRegistry.find("KB_SCAN")).thenReturn(Optional.of(taskHandler));
        when(taskHandler.handle(any(TaskExecutionContext.class))).thenThrow(new RuntimeException("boom"));
        when(taskRepository.completeIfActive(taskId, TaskStatus.FAILED, "boom", TaskErrorCode.HANDLER_FAILED, "boom"))
                .thenReturn(null);

        service.process(taskId, 3, 3);

        verify(taskRepository).completeIfActive(taskId, TaskStatus.FAILED, "boom", TaskErrorCode.HANDLER_FAILED, "boom");
        verify(taskEventService, never()).append(eq(running.projectId()), eq(taskId), eq(TaskEventType.FAILED), any(), anyInt(), any());
        verify(taskSecretPayloadService, never()).deleteByTaskId(taskId);
        verify(taskLogSseBroker, never()).publishTerminal(any());
    }

    @Test
    void marksTaskFailedWithoutRetryWhenCredentialIsInvalid() {
        TaskWorkerService service = service();
        UUID taskId = UUID.randomUUID();
        TaskView running = task(taskId, TaskStatus.RUNNING);
        TaskView failed = task(taskId, TaskStatus.FAILED);
        TasksRecord record = taskRecord(taskId, TaskStatus.QUEUED);
        when(taskRepository.findRecordById(taskId)).thenReturn(Optional.of(record));
        when(taskRepository.claim(taskId, "任务开始执行")).thenReturn(running);
        when(taskHandlerRegistry.find("KB_SCAN")).thenReturn(Optional.of(taskHandler));
        when(taskHandler.handle(any(TaskExecutionContext.class)))
                .thenThrow(new ApiException(HttpStatus.BAD_REQUEST, "CREDENTIAL_DECRYPT_FAILED", "SSH 凭据无法解密"));
        when(taskRepository.completeIfActive(taskId, TaskStatus.FAILED, "SSH 凭据无法解密", TaskErrorCode.CREDENTIAL_DECRYPT_FAILED, "SSH 凭据无法解密"))
                .thenReturn(failed);

        service.process(taskId, 1, 3);

        verify(taskRepository, never()).markRetry(any(), anyInt(), any(), any(), any());
        verify(taskRepository).completeIfActive(taskId, TaskStatus.FAILED, "SSH 凭据无法解密", TaskErrorCode.CREDENTIAL_DECRYPT_FAILED, "SSH 凭据无法解密");
        verify(taskEventService).append(failed.projectId(), taskId, TaskEventType.FAILED, TaskStatus.FAILED, failed.progress(), failed.message());
        verify(taskSecretPayloadService).deleteByTaskId(taskId);
    }

    @Test
    void deletesTemporarySecretsWhenTaskIsCancelledDuringHandling() {
        TaskWorkerService service = service();
        UUID taskId = UUID.randomUUID();
        TaskView running = task(taskId, TaskStatus.RUNNING);
        TaskView cancelled = task(taskId, TaskStatus.CANCELLED);
        TasksRecord record = taskRecord(taskId, TaskStatus.QUEUED);
        when(taskRepository.findRecordById(taskId)).thenReturn(Optional.of(record));
        when(taskRepository.claim(taskId, "任务开始执行")).thenReturn(running);
        when(taskHandlerRegistry.find("KB_SCAN")).thenReturn(Optional.of(taskHandler));
        when(taskHandler.handle(any(TaskExecutionContext.class))).thenThrow(new TaskCancelledException("cancelled"));
        when(taskRepository.findById(taskId)).thenReturn(Optional.of(running));
        when(taskRepository.completeIfActive(taskId, TaskStatus.CANCELLED, "任务已取消", null, null)).thenReturn(cancelled);

        service.process(taskId);

        verify(taskRepository).completeIfActive(taskId, TaskStatus.CANCELLED, "任务已取消", null, null);
        verify(taskSecretPayloadService).deleteByTaskId(taskId);
        verify(taskLogSseBroker).publishTerminal(cancelled);
    }

    @Test
    void preservesTaskExecutionErrorCodeWhenHandlerThrowsExecutionException(CapturedOutput output) {
        TaskWorkerService service = service();
        UUID taskId = UUID.randomUUID();
        TaskView running = task(taskId, TaskStatus.RUNNING);
        TaskView failed = task(taskId, TaskStatus.FAILED);
        TasksRecord record = taskRecord(taskId, TaskStatus.QUEUED);
        when(taskRepository.findRecordById(taskId)).thenReturn(Optional.of(record));
        when(taskRepository.claim(taskId, "任务开始执行")).thenReturn(running);
        when(taskHandlerRegistry.find("KB_SCAN")).thenReturn(Optional.of(taskHandler));
        when(taskHandler.handle(any(TaskExecutionContext.class)))
                .thenThrow(new TaskExecutionException(TaskErrorCode.INPUT_INVALID, "任务输入快照无法解析", new RuntimeException("secret=raw-value")));
        when(taskRepository.completeIfActive(taskId, TaskStatus.FAILED, "任务输入快照无法解析", TaskErrorCode.INPUT_INVALID, "任务输入快照无法解析"))
                .thenReturn(failed);

        service.process(taskId);

        verify(taskRepository).completeIfActive(taskId, TaskStatus.FAILED, "任务输入快照无法解析", TaskErrorCode.INPUT_INVALID, "任务输入快照无法解析");
        assertThat(output.getOut() + output.getErr())
                .contains("causeClass=java.lang.RuntimeException")
                .contains("secret=[REDACTED]")
                .doesNotContain("raw-value");
    }

    @Test
    void usesDefaultSafeMessageWhenHandlerThrowsBlankMessage() {
        TaskWorkerService service = service();
        UUID taskId = UUID.randomUUID();
        TaskView running = task(taskId, TaskStatus.RUNNING);
        TaskView failed = task(taskId, TaskStatus.FAILED);
        TasksRecord record = taskRecord(taskId, TaskStatus.QUEUED);
        when(taskRepository.findRecordById(taskId)).thenReturn(Optional.of(record));
        when(taskRepository.claim(taskId, "任务开始执行")).thenReturn(running);
        when(taskHandlerRegistry.find("KB_SCAN")).thenReturn(Optional.of(taskHandler));
        when(taskHandler.handle(any(TaskExecutionContext.class))).thenThrow(new RuntimeException(" "));
        when(taskRepository.completeIfActive(taskId, TaskStatus.FAILED, "任务执行失败", TaskErrorCode.HANDLER_FAILED, "任务执行失败")).thenReturn(failed);

        service.process(taskId);

        verify(taskRepository).completeIfActive(taskId, TaskStatus.FAILED, "任务执行失败", TaskErrorCode.HANDLER_FAILED, "任务执行失败");
    }

    @Test
    void mapsCredentialAndGenericApiCodesWithoutLosingSpecificMeaning() {
        TaskWorkerService service = service();
        String notFound = invoke(service, "taskErrorCode", "CREDENTIAL_NOT_FOUND");
        String decryptFailed = invoke(service, "taskErrorCode", "CREDENTIAL_DECRYPT_FAILED");
        String credentialInvalid = invoke(service, "taskErrorCode", "CREDENTIAL_EXPIRED");
        String custom = invoke(service, "taskErrorCode", "CUSTOM_CODE");
        String missing = invoke(service, "taskErrorCode", (Object) null);
        String blank = invoke(service, "taskErrorCode", "  ");
        assertThat(notFound).isEqualTo(TaskErrorCode.CREDENTIAL_NOT_FOUND);
        assertThat(decryptFailed).isEqualTo(TaskErrorCode.CREDENTIAL_DECRYPT_FAILED);
        assertThat(credentialInvalid).isEqualTo(TaskErrorCode.CREDENTIAL_INVALID);
        assertThat(custom).isEqualTo("CUSTOM_CODE");
        assertThat(missing).isEqualTo(TaskErrorCode.HANDLER_FAILED);
        assertThat(blank).isEqualTo(TaskErrorCode.HANDLER_FAILED);
    }

    @Test
    void sanitizesMailAndWorkerMessagesAtBoundary() {
        TaskWorkerService service = service();
        assertThat((String) invoke(service, "safeMailLine", (Object) null)).isEmpty();
        assertThat((String) invoke(service, "safeMailLine", "  ")).isEmpty();
        assertThat((String) invoke(service, "safeMailLine", "tokenValue ready")).isEqualTo("token=****** ready");
        assertThat((String) invoke(service, "safeMessage", new RuntimeException((String) null)))
                .isEqualTo("任务执行失败");
        assertThat((String) invoke(service, "safeMessage", " ")).isEqualTo("任务执行失败");
        assertThat((String) invoke(service, "safeMessage", "password=raw Authorization: Bearer abc C:\\secret\\file"))
                .doesNotContain("raw", "abc", "C:/secret/file");
        assertThat((String) invoke(service, "safeMessage", "x".repeat(600))).hasSize(500);
    }

    @Test
    void ignoresLateCompletionWithoutDuplicatingTerminalEvents() {
        TaskWorkerService service = service();
        UUID taskId = UUID.randomUUID();
        TaskView running = task(taskId, TaskStatus.RUNNING);
        when(taskRepository.findRecordById(taskId)).thenReturn(Optional.of(taskRecord(taskId, TaskStatus.QUEUED)));
        when(taskRepository.claim(taskId, "任务开始执行")).thenReturn(running);
        when(taskHandlerRegistry.find("KB_SCAN")).thenReturn(Optional.of(taskHandler));
        when(taskHandler.handle(any())).thenReturn(TaskHandlerResult.success("done"));
        when(taskRepository.completeIfActive(taskId, TaskStatus.SUCCEEDED, "done", null, null)).thenReturn(null);

        service.process(taskId);

        verify(taskEventService, never()).append(any(), eq(taskId), eq(TaskEventType.SUCCEEDED), any(), anyInt(), any());
        verifyNoInteractions(taskLogSseBroker, taskSecretPayloadService);
    }

    @Test
    void notifiesOnlyUsersWithUsableEmailAndContainsSanitizedSummary() {
        TaskWorkerService service = service();
        TaskView task = task(UUID.randomUUID(), TaskStatus.SUCCEEDED);
        when(mailConfigService.currentConfig()).thenReturn(new MailConfig(true, true, "host", 25, null, null, null, true, false, 5000, 10000, "from@test"));
        UserView nullEmail = user(task.createdBy(), null);
        UserView blankEmail = user(task.createdBy(), "  ");
        UserView valid = user(task.createdBy(), "user@test.invalid");
        when(userRepository.findById(task.createdBy())).thenReturn(Optional.empty(), Optional.of(nullEmail), Optional.of(blankEmail), Optional.of(valid));

        invoke(service, "notifyTaskTerminal", task);
        invoke(service, "notifyTaskTerminal", task);
        invoke(service, "notifyTaskTerminal", task);
        invoke(service, "notifyTaskTerminal", task);

        verify(mailDeliveryService).sendTaskCompleted(eq("user@test.invalid"), any(), any());
    }

    @Test
    void terminalNotificationAndSecretCleanupFailuresDoNotChangeTaskOutcome() {
        TaskWorkerService service = service();
        TaskView task = task(UUID.randomUUID(), TaskStatus.FAILED);
        when(mailConfigService.currentConfig()).thenThrow(new IllegalStateException("mail unavailable"));
        when(taskSecretPayloadService.deleteByTaskId(task.id())).thenThrow(new IllegalStateException("cleanup unavailable"));

        invoke(service, "notifyTaskTerminal", task);
        invoke(service, "cleanupTaskSecrets", task);
    }

    @SuppressWarnings("unchecked")
    private <T> T invoke(TaskWorkerService service, String method, Object... arguments) {
        return (T) ReflectionTestUtils.invokeMethod(service, method, arguments);
    }

    private TaskWorkerService service() {
        lenient().when(attempts.claim(any(), any())).thenAnswer(invocation -> {
            TaskView task = taskRepository.claim(invocation.getArgument(0), "任务开始执行");
            if (task == null) return null;
            var handle = runtimeHandleRepository.createTaskHandle(task.id(), task.projectId(), invocation.getArgument(1));
            if (handle == null) throw new TaskAttemptLostException();
            return new TaskAttemptService.Claim(task, handle);
        });
        lenient().when(attempts.publish(any(), any(), any())).thenAnswer(invocation ->
                ((java.util.function.Supplier<?>) invocation.getArgument(2)).get());
        TaskLogService taskLogService = new TaskLogService(taskLogRepository, properties());
        lenient().when(mailConfigService.currentConfig()).thenReturn(new MailConfig(false, true, null, 0, null, null, null, true, false, 5000, 10000, null));
        lenient().when(runtimeHandleRepository.createTaskHandle(any(), any(), any()))
                .thenAnswer(invocation -> new TaskRuntimeHandleView(
                        UUID.randomUUID(),
                        invocation.getArgument(0),
                        invocation.getArgument(1),
                        invocation.getArgument(2),
                        TaskRuntimeHandleType.TASK,
                        TaskRuntimeHandleStatus.ACTIVE,
                        null,
                        null,
                        null,
                        null,
                        null,
                        null,
                        OffsetDateTime.now(),
                        OffsetDateTime.now(),
                        null,
                        null,
                        null
                ));
        return new TaskWorkerService(taskRepository, taskEventService, taskHandlerRegistry, taskLogService,
                taskLogEventService, taskLogSseBroker, new ObjectMapper(),
                mailDeliveryService, mailConfigService, userRepository, runtimeHandleRepository,
                taskSecretPayloadService,
                new TaskExecutionRegistry(), new WorkerInstanceIdProvider(workerProperties()), attempts);
    }

    private RvPortProperties properties() {
        return new RvPortProperties(
                new RvPortProperties.Runtime(Path.of("target", "test-task-logs").toString(), "archives", "uploads", "sources"),
                null,
                new RvPortProperties.Worker(false)
        );
    }

    private WorkerProperties workerProperties() {
        return new WorkerProperties(false, null, null, 1, 8, 10, 60);
    }

    private TaskView task(UUID taskId, TaskStatus status) {
        return new TaskView(
                taskId,
                UUID.randomUUID(),
                "KB_SCAN",
                status,
                status == TaskStatus.SUCCEEDED ? 100 : 0,
                "任务开始执行",
                UUID.randomUUID(),
                OffsetDateTime.now(),
                OffsetDateTime.now(),
                status == TaskStatus.RUNNING ? OffsetDateTime.now() : null,
                status == TaskStatus.SUCCEEDED || status == TaskStatus.FAILED ? OffsetDateTime.now() : null,
                300,
                status == TaskStatus.FAILED ? TaskErrorCode.HANDLER_NOT_FOUND : null,
                null,
                0
        );
    }

    private UserView user(UUID id, String email) {
        OffsetDateTime now = OffsetDateTime.now();
        return new UserView(id, "user", "User", email, false, false, UserStatus.ACTIVE, null, now, now);
    }

    private TasksRecord taskRecord(UUID taskId, TaskStatus status) {
        TasksRecord record = new TasksRecord();
        record.setId(taskId);
        record.setProjectId(UUID.randomUUID());
        record.setType("KB_SCAN");
        record.setStatus(status.name());
        record.setProgress(0);
        record.setMessage("任务消息");
        record.setInputSnapshot(JSONB.valueOf("{}"));
        record.setCreatedBy(UUID.randomUUID());
        record.setCreatedAt(OffsetDateTime.now());
        record.setRetryCount(0);
        return record;
    }
}
