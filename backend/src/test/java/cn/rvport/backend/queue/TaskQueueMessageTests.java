package cn.rvport.backend.queue;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.UUID;

import org.junit.jupiter.api.Test;

class TaskQueueMessageTests {

    @Test
    void requiresTaskIdAndTaskType() {
        assertThatThrownBy(() -> new TaskQueueMessage(null, "KB_SCAN", UUID.randomUUID(), null))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("taskId");

        assertThatThrownBy(() -> new TaskQueueMessage(UUID.randomUUID(), " ", UUID.randomUUID(), null))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("taskType");
    }

    @Test
    void defaultsCreatedAtWhenMissing() {
        TaskQueueMessage message = new TaskQueueMessage(UUID.randomUUID(), "KB_SCAN", null, null);

        assertThat(message.createdAt()).isNotNull();
    }

    @Test
    void defaultsAndIncrementsAttempt() {
        TaskQueueMessage message = new TaskQueueMessage(UUID.randomUUID(), "KB_SCAN", null, null, 0);

        assertThat(message.attempt()).isEqualTo(1);
        assertThat(message.nextAttempt().attempt()).isEqualTo(2);
        assertThat(message.nextAttempt().taskId()).isEqualTo(message.taskId());
    }
}
