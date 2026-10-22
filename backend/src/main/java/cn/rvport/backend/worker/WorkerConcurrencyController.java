package cn.rvport.backend.worker;

import java.util.concurrent.atomic.AtomicInteger;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.core.MessageListenerContainer;
import org.springframework.amqp.rabbit.listener.RabbitListenerEndpointRegistry;
import org.springframework.amqp.rabbit.listener.SimpleMessageListenerContainer;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(prefix = "rvport.worker", name = "enabled", havingValue = "true")
public class WorkerConcurrencyController {

    private static final Logger log = LoggerFactory.getLogger(WorkerConcurrencyController.class);

    private final RabbitListenerEndpointRegistry registry;
    private final AtomicInteger appliedConcurrency = new AtomicInteger(1);

    public WorkerConcurrencyController(RabbitListenerEndpointRegistry registry) {
        this.registry = registry;
    }

    public int apply(int concurrencyLimit) {
        MessageListenerContainer container = registry.getListenerContainer(TaskWorkerListener.TASK_LISTENER_ID);
        if (container == null) {
            log.debug("Task worker listener container is not ready");
            return 0;
        }
        if (concurrencyLimit <= 0) {
            container.stop();
            return 0;
        }
        if (container instanceof SimpleMessageListenerContainer simpleContainer) {
            int previousConcurrency = appliedConcurrency.get();
            if (concurrencyLimit > previousConcurrency) {
                simpleContainer.setMaxConcurrentConsumers(concurrencyLimit);
                simpleContainer.setConcurrentConsumers(concurrencyLimit);
            } else {
                simpleContainer.setConcurrentConsumers(concurrencyLimit);
                simpleContainer.setMaxConcurrentConsumers(concurrencyLimit);
            }
            simpleContainer.setPrefetchCount(1);
            appliedConcurrency.set(concurrencyLimit);
        }
        if (!container.isRunning()) {
            container.start();
        }
        return concurrencyLimit;
    }
}
