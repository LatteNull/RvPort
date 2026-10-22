package cn.rvport.backend.task;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class TaskLogIncrementServiceTests {

    @Mock
    private TaskLogEventRepository repository;

    @Test
    void aggregatesEventsInOrderAndAdvancesCursor() {
        UUID taskId = UUID.randomUUID();
        when(repository.listAfter(taskId, 10, 4)).thenReturn(List.of(
                event(12, taskId, TaskLogType.STDOUT, "one\n"),
                event(15, taskId, TaskLogType.STDERR, "warn\n")
        ));

        TaskLogIncrementResponse response = new TaskLogIncrementService(repository)
                .read(taskId, new TaskLogIncrementRequest(10, 3));

        assertThat(response.fromEventId()).isEqualTo(12);
        assertThat(response.latestEventId()).isEqualTo(15);
        assertThat(response.hasMore()).isFalse();
        assertThat(response.logs().get("merged").content()).isEqualTo("[STDOUT] one\n[STDERR] warn\n");
        assertThat(response.logs().get("stdout").content()).isEqualTo("one\n");
        assertThat(response.logs().get("stderr").content()).isEqualTo("warn\n");
        assertThat(response.logs().get("merged").returnedEvents()).isEqualTo(2);
        verify(repository).listAfter(taskId, 10, 4);
    }

    @Test
    void returnsEmptyContentWithoutMovingCursor() {
        UUID taskId = UUID.randomUUID();
        when(repository.listAfter(taskId, 99, 501)).thenReturn(List.of());

        TaskLogIncrementResponse response = new TaskLogIncrementService(repository)
                .read(taskId, new TaskLogIncrementRequest(99, 500));

        assertThat(response.fromEventId()).isNull();
        assertThat(response.latestEventId()).isEqualTo(99);
        assertThat(response.hasMore()).isFalse();
        assertThat(response.logs().values()).allSatisfy(log -> {
            assertThat(log.content()).isEmpty();
            assertThat(log.returnedEvents()).isZero();
        });
    }

    @Test
    void stopsAtEventLimitAndReportsMore() {
        UUID taskId = UUID.randomUUID();
        when(repository.listAfter(taskId, 0, 3)).thenReturn(List.of(
                event(1, taskId, TaskLogType.STDOUT, "a"),
                event(3, taskId, TaskLogType.STDOUT, "b"),
                event(8, taskId, TaskLogType.STDERR, "c")
        ));

        TaskLogIncrementResponse response = new TaskLogIncrementService(repository)
                .read(taskId, new TaskLogIncrementRequest(0, 2));

        assertThat(response.latestEventId()).isEqualTo(3);
        assertThat(response.hasMore()).isTrue();
        assertThat(response.logs().get("merged").returnedEvents()).isEqualTo(2);
    }

    @Test
    void stopsBeforeResponseByteLimitWithoutSplittingEvent() {
        UUID taskId = UUID.randomUUID();
        List<TaskLogEventView> events = new ArrayList<>();
        for (int index = 1; index <= 140; index++) {
            events.add(event(index, taskId, TaskLogType.STDOUT, "x".repeat(4000)));
        }
        when(repository.listAfter(taskId, 0, 501)).thenReturn(events);

        TaskLogIncrementResponse response = new TaskLogIncrementService(repository)
                .read(taskId, new TaskLogIncrementRequest(0, 500));

        assertThat(response.hasMore()).isTrue();
        assertThat(response.logs().get("merged").returnedEvents()).isBetween(1, 139);
        assertThat(response.latestEventId()).isEqualTo(response.logs().get("merged").returnedEvents());
    }

    @Test
    void propagatesRepositoryReadFailure() {
        UUID taskId = UUID.randomUUID();
        when(repository.listAfter(taskId, 0, 501)).thenThrow(new IllegalStateException("database unavailable"));

        assertThatThrownBy(() -> new TaskLogIncrementService(repository)
                .read(taskId, new TaskLogIncrementRequest(0, 500)))
                .isInstanceOf(IllegalStateException.class)
                .hasMessage("database unavailable");
    }

    private TaskLogEventView event(long id, UUID taskId, TaskLogType type, String content) {
        return new TaskLogEventView(id, UUID.randomUUID(), taskId, type, id, content, OffsetDateTime.now());
    }
}
