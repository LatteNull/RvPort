package cn.rvport.backend.worker;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.clearInvocations;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InOrder;
import org.mockito.Mock;
import org.mockito.Mockito;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.amqp.rabbit.listener.RabbitListenerEndpointRegistry;
import org.springframework.amqp.rabbit.listener.SimpleMessageListenerContainer;

@ExtendWith(MockitoExtension.class)
class WorkerConcurrencyControllerTests {

    @Mock
    private RabbitListenerEndpointRegistry registry;

    @Mock
    private SimpleMessageListenerContainer container;

    @Test
    void appliesPositiveConcurrencyAndStartsStoppedListener() {
        when(registry.getListenerContainer(TaskWorkerListener.TASK_LISTENER_ID)).thenReturn(container);
        WorkerConcurrencyController controller = new WorkerConcurrencyController(registry);

        int activeConcurrency = controller.apply(3);

        assertThat(activeConcurrency).isEqualTo(3);
        InOrder order = Mockito.inOrder(container);
        order.verify(container).setMaxConcurrentConsumers(3);
        order.verify(container).setConcurrentConsumers(3);
        verify(container).setPrefetchCount(1);
        verify(container).start();
    }

    @Test
    void lowersConcurrencyBeforeLoweringMaxConcurrency() {
        when(registry.getListenerContainer(TaskWorkerListener.TASK_LISTENER_ID)).thenReturn(container);
        WorkerConcurrencyController controller = new WorkerConcurrencyController(registry);
        controller.apply(4);
        clearInvocations(container);

        int activeConcurrency = controller.apply(1);

        assertThat(activeConcurrency).isEqualTo(1);
        InOrder order = Mockito.inOrder(container);
        order.verify(container).setConcurrentConsumers(1);
        order.verify(container).setMaxConcurrentConsumers(1);
        verify(container).setPrefetchCount(1);
        verify(container).start();
    }

    @Test
    void zeroConcurrencyStopsListenerWithoutCancellingRunningTasks() {
        when(registry.getListenerContainer(TaskWorkerListener.TASK_LISTENER_ID)).thenReturn(container);
        WorkerConcurrencyController controller = new WorkerConcurrencyController(registry);

        int activeConcurrency = controller.apply(0);

        assertThat(activeConcurrency).isZero();
        verify(container).stop();
        verify(container, never()).setConcurrentConsumers(0);
        verify(container, never()).setMaxConcurrentConsumers(0);
    }

    @Test
    void missingListenerContainerIsEdgeCaseNoop() {
        when(registry.getListenerContainer(TaskWorkerListener.TASK_LISTENER_ID)).thenReturn(null);
        WorkerConcurrencyController controller = new WorkerConcurrencyController(registry);

        assertThat(controller.apply(2)).isZero();
    }
}
