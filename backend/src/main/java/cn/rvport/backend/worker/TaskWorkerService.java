package cn.rvport.backend.worker;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.jooq.tables.records.TasksRecord;
import cn.rvport.backend.mail.MailConfigService;
import cn.rvport.backend.mail.MailDeliveryService;
import cn.rvport.backend.task.TaskErrorCode;
import cn.rvport.backend.task.TaskEventService;
import cn.rvport.backend.task.TaskEventType;
import cn.rvport.backend.task.TaskExecutionException;
import cn.rvport.backend.task.TaskLogService;
import cn.rvport.backend.task.TaskLogEventService;
import cn.rvport.backend.task.TaskLogSseBroker;
import cn.rvport.backend.task.TaskRepository;
import cn.rvport.backend.task.TaskRuntimeHandleRepository;
import cn.rvport.backend.task.TaskRuntimeHandleStatus;
import cn.rvport.backend.task.TaskRuntimeHandleView;
import cn.rvport.backend.task.TaskSecretPayloadService;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.task.TaskView;
import cn.rvport.backend.user.UserRepository;
import cn.rvport.backend.user.UserView;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

@Service
public class TaskWorkerService {

    private static final Logger log = LoggerFactory.getLogger(TaskWorkerService.class);

    private final TaskRepository taskRepository;
    private final TaskEventService taskEventService;
    private final TaskHandlerRegistry taskHandlerRegistry;
    private final TaskLogService taskLogService;
    private final TaskLogEventService taskLogEventService;
    private final TaskLogSseBroker taskLogSseBroker;
    private final ObjectMapper objectMapper;
    private final MailDeliveryService mailDeliveryService;
    private final MailConfigService mailConfigService;
    private final UserRepository userRepository;
    private final TaskRuntimeHandleRepository runtimeHandleRepository;
    private final TaskSecretPayloadService taskSecretPayloadService;
    private final TaskExecutionRegistry taskExecutionRegistry;
    private final WorkerInstanceIdProvider workerInstanceIdProvider;
    private final TaskRetryPolicy taskRetryPolicy = new TaskRetryPolicy();
    private final TaskAttemptService attempts;

    public TaskWorkerService(
            TaskRepository taskRepository,
            TaskEventService taskEventService,
            TaskHandlerRegistry taskHandlerRegistry,
            TaskLogService taskLogService,
            TaskLogEventService taskLogEventService,
            TaskLogSseBroker taskLogSseBroker,
            ObjectMapper objectMapper,
            MailDeliveryService mailDeliveryService,
            MailConfigService mailConfigService,
            UserRepository userRepository,
            TaskRuntimeHandleRepository runtimeHandleRepository,
            TaskSecretPayloadService taskSecretPayloadService,
            TaskExecutionRegistry taskExecutionRegistry,
            WorkerInstanceIdProvider workerInstanceIdProvider,
            TaskAttemptService attempts
    ) {
        this.taskRepository = taskRepository;
        this.taskEventService = taskEventService;
        this.taskHandlerRegistry = taskHandlerRegistry;
        this.taskLogService = taskLogService;
        this.taskLogEventService = taskLogEventService;
        this.taskLogSseBroker = taskLogSseBroker;
        this.objectMapper = objectMapper;
        this.mailDeliveryService = mailDeliveryService;
        this.mailConfigService = mailConfigService;
        this.userRepository = userRepository;
        this.runtimeHandleRepository = runtimeHandleRepository;
        this.taskSecretPayloadService = taskSecretPayloadService;
        this.taskExecutionRegistry = taskExecutionRegistry;
        this.workerInstanceIdProvider = workerInstanceIdProvider;
        this.attempts = attempts;
    }

    public void process(UUID taskId) {
        process(taskId, 1, 1);
    }

    public void process(UUID taskId, int attempt, int maxAttempts) {
        TasksRecord existing = taskRepository.findRecordById(taskId).orElse(null);
        if (existing == null) {
            log.warn("Task message skipped because task does not exist taskId={}", taskId);
            return;
        }

        TaskAttemptService.Claim claim = attempts.claim(taskId, workerInstanceIdProvider.workerInstanceId());
        if (claim == null) {
            log.info("Task message skipped because task is not claimable taskId={} status={}", taskId, existing.getStatus());
            return;
        }
        TaskView claimed = claim.task();
        TaskRuntimeHandleView runtimeHandle = claim.handle();

        Boolean started = current(claim, () -> {
        taskEventService.append(
                claimed.projectId(),
                claimed.id(),
                TaskEventType.STARTED,
                TaskStatus.RUNNING,
                claimed.progress(),
                claimed.message()
        );
        return true;
        });
        if (!Boolean.TRUE.equals(started)) {
            return;
        }

        TaskHandler handler = taskHandlerRegistry.find(claimed.type()).orElse(null);
        if (handler == null) {
            current(claim, () -> {
                fail(claimed, TaskErrorCode.HANDLER_NOT_FOUND, "任务类型没有可用处理器");
                runtimeHandleRepository.markError(runtimeHandle.id(), TaskRuntimeHandleStatus.FAILED,
                        TaskErrorCode.HANDLER_NOT_FOUND, "任务类型没有可用处理器");
                return null;
            });
            return;
        }

        RunningTaskHandle runningTaskHandle = new RunningTaskHandle(
                claimed.id(),
                runtimeHandle.id(),
                Thread.currentThread(),
                runtimeHandleRepository
        );
        taskExecutionRegistry.register(runningTaskHandle);

        try {
            TaskExecutionContext context = new DefaultTaskExecutionContext(
                    claimed,
                    existing.getInputSnapshot(),
                    taskRepository,
                    taskEventService,
                    taskLogService,
                    taskLogEventService,
                    objectMapper,
                    runningTaskHandle,
                    null
            ).withAttemptService(attempts);
            TaskHandlerResult result = handler.handle(context);
            TaskView completed = current(claim, () -> {
                TaskView value = taskRepository.completeIfActive(
                    claimed.id(),
                    TaskStatus.SUCCEEDED,
                    result.message(),
                    null,
                    null
            );
            if (value != null) {
                taskEventService.append(
                        value.projectId(),
                        value.id(),
                        TaskEventType.SUCCEEDED,
                        TaskStatus.SUCCEEDED,
                        value.progress(),
                        value.message()
                );
                runningTaskHandle.markTerminated(TaskRuntimeHandleStatus.TERMINATED);
            }
            return value;
            });
            if (completed == null) {
                return;
            }
            cleanupTaskSecrets(completed);
            notifyTaskTerminal(completed);
            taskLogSseBroker.publishTerminal(completed);
        } catch (TaskAttemptLostException ex) {
            log.info("Task attempt stopped after losing ownership taskId={} handleId={}", taskId, runtimeHandle.id());
        } catch (TaskCancelledException ex) {
            TaskView current = taskRepository.findById(claimed.id()).orElse(claimed);
            if (taskRepository.isTerminal(current.status()) && current.status() != TaskStatus.CANCELLED) {
                return;
            }
            if (!taskRepository.isTerminal(current.status())) {
                current = current(claim, () -> {
                    TaskView cancelled = taskRepository.completeIfActive(claimed.id(), TaskStatus.CANCELLED, "任务已取消", null, null);
                    if (cancelled != null) {
                        taskEventService.append(cancelled.projectId(), cancelled.id(), TaskEventType.CANCELLED,
                                TaskStatus.CANCELLED, cancelled.progress(), cancelled.message());
                    }
                    return cancelled;
                });
                if (current == null) {
                    return;
                }
            }
            runningTaskHandle.markTerminated(TaskRuntimeHandleStatus.CANCELLED);
            cleanupTaskSecrets(current);
            taskLogSseBroker.publishTerminal(current);
        } catch (TaskExecutionException ex) {
            if (ex.getCause() == null) {
                log.warn("Task execution failed taskId={} type={} code={} message={}",
                        claimed.id(), claimed.type(), ex.errorCode(), safeMessage(ex.safeMessage()));
            } else {
                log.warn("Task execution failed taskId={} type={} code={} message={} causeClass={} causeMessage={}",
                        claimed.id(), claimed.type(), ex.errorCode(), safeMessage(ex.safeMessage()),
                        ex.getCause().getClass().getName(), safeMessage(ex.getCause().getMessage()), sanitizedThrowable(ex));
            }
            retryOrFail(claim, attempt, maxAttempts, ex.errorCode(), ex.safeMessage(), ex);
        } catch (ApiException ex) {
            String errorCode = taskErrorCode(ex.code());
            log.warn("Task handler rejected request taskId={} type={} code={} message={}",
                    claimed.id(), claimed.type(), errorCode, ex.getMessage());
            retryOrFail(claim, attempt, maxAttempts, errorCode, ex.getMessage(), ex);
        } catch (RuntimeException ex) {
            log.warn("Task handler failed taskId={} type={}", claimed.id(), claimed.type(), ex);
            retryOrFail(claim, attempt, maxAttempts, TaskErrorCode.HANDLER_FAILED, safeMessage(ex), ex);
        } finally {
            taskExecutionRegistry.remove(runningTaskHandle);
        }
    }

    private void retryOrFail(
            TaskAttemptService.Claim claim,
            int attempt,
            int maxAttempts,
            String errorCode,
            String errorMessage,
            RuntimeException cause
    ) {
        TaskView task = claim.task();
        Boolean retry = current(claim, () -> {
        if (taskRetryPolicy.shouldRetry(errorCode) && attempt < maxAttempts) {
            TaskView queued = taskRepository.markRetry(
                    task.id(),
                    attempt,
                    "任务执行失败，等待第 " + (attempt + 1) + " 次重试",
                    errorCode,
                    errorMessage
            );
            if (queued == null) {
                log.warn("Task retry skipped because task no longer exists taskId={}", task.id());
                return false;
            }
            taskEventService.append(
                    queued.projectId(),
                    queued.id(),
                    TaskEventType.QUEUED,
                    TaskStatus.QUEUED,
                    queued.progress(),
                    queued.message()
            );
            runtimeHandleRepository.markError(claim.handle().id(), TaskRuntimeHandleStatus.FAILED, errorCode, errorMessage);
            return true;
        }
        fail(task, errorCode, errorMessage);
        runtimeHandleRepository.markError(claim.handle().id(), TaskRuntimeHandleStatus.FAILED, errorCode, errorMessage);
        return false;
        });
        if (Boolean.TRUE.equals(retry)) {
            throw new TaskRetryableException(errorMessage, cause);
        }
    }

    private <T> T current(TaskAttemptService.Claim claim, java.util.function.Supplier<T> operation) {
        try {
            return attempts.publish(claim.task().id(), claim.handle().id(), operation);
        } catch (TaskAttemptLostException ex) {
            log.info("Late task write ignored taskId={} handleId={}", claim.task().id(), claim.handle().id());
            return null;
        }
    }

    private String taskErrorCode(String apiErrorCode) {
        if ("CREDENTIAL_NOT_FOUND".equals(apiErrorCode)) {
            return TaskErrorCode.CREDENTIAL_NOT_FOUND;
        }
        if ("CREDENTIAL_DECRYPT_FAILED".equals(apiErrorCode)) {
            return TaskErrorCode.CREDENTIAL_DECRYPT_FAILED;
        }
        if (apiErrorCode != null && apiErrorCode.startsWith("CREDENTIAL_")) {
            return TaskErrorCode.CREDENTIAL_INVALID;
        }
        return apiErrorCode == null || apiErrorCode.isBlank() ? TaskErrorCode.HANDLER_FAILED : apiErrorCode;
    }

    private void fail(TaskView task, String errorCode, String errorMessage) {
        TaskView failed = taskRepository.completeIfActive(
                task.id(),
                TaskStatus.FAILED,
                errorMessage,
                errorCode,
                errorMessage
        );
        if (failed == null) {
            log.warn("Task failure skipped because task no longer exists taskId={}", task.id());
            return;
        }
        taskEventService.append(
                failed.projectId(),
                failed.id(),
                TaskEventType.FAILED,
                TaskStatus.FAILED,
                failed.progress(),
                failed.message()
        );
        cleanupTaskSecrets(failed);
        Runnable notification = () -> {
            notifyTaskTerminal(failed);
            taskLogSseBroker.publishTerminal(failed);
        };
        if (org.springframework.transaction.support.TransactionSynchronizationManager.isSynchronizationActive()) {
            org.springframework.transaction.support.TransactionSynchronizationManager.registerSynchronization(
                    new org.springframework.transaction.support.TransactionSynchronization() {
                        @Override
                        public void afterCommit() {
                            notification.run();
                        }
                    });
        } else {
            notification.run();
        }
    }

    private void cleanupTaskSecrets(TaskView task) {
        try {
            int deleted = taskSecretPayloadService.deleteByTaskId(task.id());
            if (deleted > 0) {
                log.debug("Task temporary secret payloads deleted taskId={} count={}", task.id(), deleted);
            }
        } catch (RuntimeException ex) {
            log.warn("Task temporary secret cleanup failed taskId={}", task.id(), ex);
        }
    }

    private void notifyTaskTerminal(TaskView task) {
        try {
            if (!mailConfigService.currentConfig().enabled()) {
                return;
            }
            UserView user = userRepository.findById(task.createdBy()).orElse(null);
            if (user == null || user.email() == null || user.email().isBlank()) {
                return;
            }
            String subject = "RvPort 任务已完成：" + task.status();
            String body = """
                    你的 RvPort 任务已进入终态。

                    任务 ID: %s
                    任务类型: %s
                    任务状态: %s
                    摘要: %s

                    请登录 RvPort 查看详情。
                    """.formatted(task.id(), task.type(), task.status(), safeMailLine(task.message()));
            mailDeliveryService.sendTaskCompleted(user.email(), subject, body);
        } catch (RuntimeException ex) {
            log.warn("Task terminal mail notification failed taskId={}", task.id(), ex);
        }
    }

    private String safeMailLine(String value) {
        if (value == null || value.isBlank()) {
            return "";
        }
        return value.replaceAll("(?i)(password|token|privateKey|private_key|passphrase|secret)\\S*", "$1=******");
    }

    private String safeMessage(RuntimeException ex) {
        String message = ex.getMessage();
        return safeMessage(message);
    }

    private String safeMessage(String message) {
        if (message == null || message.isBlank()) {
            return "任务执行失败";
        }
        String sanitized = message
                .replace('\\', '/')
                .replaceAll("(?i)(password|private[_-]?key|passphrase|secret|token)(\\s*[=:]\\s*)\\S+", "$1$2[REDACTED]")
                .replaceAll("(?i)authorization:\\s*bearer\\s+\\S+", "Authorization: Bearer [REDACTED]")
                .replaceAll("(?i)[A-Za-z]:/[^\\s]+", "<server-path-redacted>")
                .replaceAll("(^|\\s)/[^\\s]+", "$1<server-path-redacted>");
        return sanitized.length() > 500 ? sanitized.substring(0, 500) : sanitized;
    }

    private RuntimeException sanitizedThrowable(TaskExecutionException ex) {
        RuntimeException sanitized = new RuntimeException(safeMessage(ex.getMessage()), sanitizedCause(ex.getCause()));
        sanitized.setStackTrace(ex.getStackTrace());
        return sanitized;
    }

    private Throwable sanitizedCause(Throwable cause) {
        if (cause == null) {
            return null;
        }
        RuntimeException sanitized = new RuntimeException(safeMessage(cause.getMessage()));
        sanitized.setStackTrace(cause.getStackTrace());
        return sanitized;
    }
}
