package cn.rvport.backend.task;

import cn.rvport.backend.config.RvPortAppMode;
import cn.rvport.backend.config.TaskSseBroadcastProperties;
import cn.rvport.backend.config.WorkerProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.ApplicationListener;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.listener.ChannelTopic;
import org.springframework.data.redis.listener.RedisMessageListenerContainer;

@Configuration
public class TaskSseRedisConfiguration {

    private static final Logger log = LoggerFactory.getLogger(TaskSseRedisConfiguration.class);

    @Bean
    RedisMessageListenerContainer taskSseRedisMessageListenerContainer(
            RedisConnectionFactory connectionFactory,
            TaskSseBroadcastProperties properties,
            WorkerProperties workerProperties,
            ObjectMapper objectMapper,
            TaskSseBroadcastInstance instance,
            TaskEventRepository taskEventRepository,
            TaskSseBroker taskSseBroker,
            TaskLogEventRepository taskLogEventRepository,
            TaskLogSseBroker taskLogSseBroker
    ) {
        RedisMessageListenerContainer container = new RedisMessageListenerContainer();
        container.setConnectionFactory(connectionFactory);
        container.setAutoStartup(false);
        if (properties.enabled() && subscribes(workerProperties.mode())) {
            container.addMessageListener(
                    new TaskSseRedisSubscriber(objectMapper, properties, instance, taskEventRepository, taskSseBroker),
                    new ChannelTopic(properties.taskEventsTopic())
            );
            container.addMessageListener(
                    new TaskLogSseRedisSubscriber(objectMapper, properties, instance, taskLogEventRepository, taskLogSseBroker),
                    new ChannelTopic(properties.taskLogEventsTopic())
            );
        }
        return container;
    }

    @Bean
    ApplicationListener<ApplicationReadyEvent> taskSseRedisMessageListenerStarter(
            RedisMessageListenerContainer taskSseRedisMessageListenerContainer,
            TaskSseBroadcastProperties properties,
            WorkerProperties workerProperties
    ) {
        return ignored -> {
            if (!properties.enabled() || !subscribes(workerProperties.mode()) || taskSseRedisMessageListenerContainer.isRunning()) {
                return;
            }
            try {
                taskSseRedisMessageListenerContainer.start();
            } catch (RuntimeException ex) {
                log.warn("SSE Redis listener startup failed mode={} error={}", workerProperties.mode(), ex.toString());
            }
        };
    }

    boolean subscribes(RvPortAppMode mode) {
        return mode == RvPortAppMode.API || mode == RvPortAppMode.COMBINED;
    }
}
