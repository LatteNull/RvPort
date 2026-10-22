package cn.rvport.backend.worker;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.when;

import java.util.List;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

class TaskHandlerRegistryTests {

    @Test
    void findsRegisteredHandlerAndReturnsEmptyForUnknownType() {
        TaskHandler handler = Mockito.mock(TaskHandler.class);
        when(handler.taskType()).thenReturn("TEST");
        TaskHandlerRegistry registry = new TaskHandlerRegistry(List.of(handler));

        assertThat(registry.find("TEST")).contains(handler);
        assertThat(registry.find("UNKNOWN")).isEmpty();
        assertThatThrownBy(() -> registry.find(null)).isInstanceOf(NullPointerException.class);
    }

    @Test
    void rejectsDuplicateTaskTypes() {
        TaskHandler first = Mockito.mock(TaskHandler.class);
        TaskHandler second = Mockito.mock(TaskHandler.class);
        when(first.taskType()).thenReturn("TEST");
        when(second.taskType()).thenReturn("TEST");

        assertThatThrownBy(() -> new TaskHandlerRegistry(List.of(first, second)))
                .isInstanceOf(IllegalStateException.class);
    }
}
