package cn.rvport.backend.queue;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.OffsetDateTime;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class TaskCancelQueueMessageTests {

    @Test
    void requiresTaskRuntimeHandleAndWorkerIdentity() {
        UUID taskId = UUID.randomUUID();
        UUID handleId = UUID.randomUUID();
        assertThatThrownBy(() -> new TaskCancelQueueMessage(null, handleId, "worker", null, null))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("taskId");
        assertThatThrownBy(() -> new TaskCancelQueueMessage(taskId, null, "worker", null, null))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("runtimeHandleId");
        for (String worker : new String[]{null, " "}) {
            assertThatThrownBy(() -> new TaskCancelQueueMessage(taskId, handleId, worker, null, null))
                    .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("workerInstanceId");
        }
    }

    @Test
    void defaultsTimestampAndPreservesExplicitValues() {
        UUID taskId = UUID.randomUUID();
        UUID handleId = UUID.randomUUID();
        TaskCancelQueueMessage defaulted = new TaskCancelQueueMessage(taskId, handleId, "worker", null, null);
        assertThat(defaulted.requestedAt()).isNotNull();

        OffsetDateTime requestedAt = OffsetDateTime.parse("2026-09-12T01:00:00Z");
        TaskCancelQueueMessage explicit = new TaskCancelQueueMessage(
                taskId, handleId, "worker", requestedAt, "USER_REQUESTED");
        assertThat(explicit.requestedAt()).isEqualTo(requestedAt);
        assertThat(explicit.reason()).isEqualTo("USER_REQUESTED");
    }
}
