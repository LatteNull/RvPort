package cn.rvport.backend.worker;

import cn.rvport.backend.config.TaskCancelQueueProperties;
import cn.rvport.backend.queue.TaskCancelQueueMessage;
import cn.rvport.backend.task.TaskRuntimeHandleRepository;
import cn.rvport.backend.task.TaskRuntimeHandleStatus;
import com.rabbitmq.client.Channel;
import java.io.IOException;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(prefix = "rvport.worker", name = "enabled", havingValue = "true")
public class TaskCancelWorkerListener {

    private static final Logger log = LoggerFactory.getLogger(TaskCancelWorkerListener.class);

    private final TaskExecutionRegistry taskExecutionRegistry;
    private final TaskRuntimeHandleRepository runtimeHandleRepository;
    private final TaskCancelQueueProperties properties;

    public TaskCancelWorkerListener(
            TaskExecutionRegistry taskExecutionRegistry,
            TaskRuntimeHandleRepository runtimeHandleRepository,
            TaskCancelQueueProperties properties
    ) {
        this.taskExecutionRegistry = taskExecutionRegistry;
        this.runtimeHandleRepository = runtimeHandleRepository;
        this.properties = properties;
    }

    @RabbitListener(queues = "#{workerCancelQueue.name}", containerFactory = "rabbitListenerContainerFactory")
    public void onMessage(TaskCancelQueueMessage cancelMessage, Message message, Channel channel) throws IOException {
        long deliveryTag = message.getMessageProperties().getDeliveryTag();
        try {
            runtimeHandleRepository.markCancelling(cancelMessage.runtimeHandleId());
            boolean cancelled = taskExecutionRegistry.cancel(cancelMessage.taskId());
            if (!cancelled) {
                runtimeHandleRepository.markError(
                        cancelMessage.runtimeHandleId(),
                        TaskRuntimeHandleStatus.CANCEL_UNKNOWN,
                        "CANCEL_HANDLE_NOT_FOUND",
                        "目标 worker 未找到运行中任务句柄"
                );
            }
            channel.basicAck(deliveryTag, false);
        } catch (RuntimeException ex) {
            int attempt = deliveryAttempt(message);
            boolean requeue = attempt < properties.maxAttempts();
            runtimeHandleRepository.markError(
                    cancelMessage.runtimeHandleId(),
                    TaskRuntimeHandleStatus.CANCEL_FAILED,
                    "CANCEL_FAILED",
                    "取消清理失败"
            );
            log.error("Task cancel worker failed taskId={} runtimeHandleId={} attempt={} maxAttempts={} requeue={}",
                    cancelMessage.taskId(),
                    cancelMessage.runtimeHandleId(),
                    attempt,
                    properties.maxAttempts(),
                    requeue,
                    ex);
            channel.basicNack(deliveryTag, false, requeue);
        }
    }

    private int deliveryAttempt(Message message) {
        Map<String, Object> headers = message.getMessageProperties().getHeaders();
        Object rawDeliveryCount = headers == null ? null : headers.get("x-delivery-count");
        if (rawDeliveryCount instanceof Number number) {
            return number.intValue() + 1;
        }
        if (rawDeliveryCount instanceof String value) {
            try {
                return Integer.parseInt(value) + 1;
            } catch (NumberFormatException ignored) {
                return 1;
            }
        }
        return 1;
    }
}
