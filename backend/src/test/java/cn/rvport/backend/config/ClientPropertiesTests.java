package cn.rvport.backend.config;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.amqp.core.AcknowledgeMode;
import org.springframework.boot.amqp.autoconfigure.RabbitProperties;
import org.springframework.core.env.StandardEnvironment;

class ClientPropertiesTests {

    @Test
    void bindsCacheAndQueueProperties() {
        StandardEnvironment environment = ApplicationYamlTestSupport.environment();
        RedisCacheProperties redis = ApplicationYamlTestSupport.bind(
                environment, "rvport.cache", RedisCacheProperties.class);
        TaskQueueProperties queue = ApplicationYamlTestSupport.bind(
                environment, "rvport.queue.task", TaskQueueProperties.class);
        RabbitProperties rabbit = ApplicationYamlTestSupport.bind(
                environment, "spring.rabbitmq", RabbitProperties.class);

        assertThat(redis.namespace()).isEqualTo("rvport:cache");
        assertThat(queue.exchange()).isEqualTo("rvport.tasks");
        assertThat(queue.queue()).isEqualTo("rvport.tasks.default");
        assertThat(queue.routingKey()).isEqualTo("task.default");
        assertThat(rabbit.getListener().getSimple().getAcknowledgeMode())
                .isEqualTo(AcknowledgeMode.MANUAL);
    }
}
