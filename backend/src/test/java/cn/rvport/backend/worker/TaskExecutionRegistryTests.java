package cn.rvport.backend.worker;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.when;

import cn.rvport.backend.task.TaskRuntimeHandleRepository;
import cn.rvport.backend.task.TaskRuntimeHandleStatus;
import java.util.UUID;
import java.time.Duration;
import org.junit.jupiter.api.Test;

class TaskExecutionRegistryTests {

    @Test
    void oldHandleRemovalDoesNotRemoveAnotherAttempt() {
        TaskRuntimeHandleRepository repository = org.mockito.Mockito.mock(TaskRuntimeHandleRepository.class);
        TaskExecutionRegistry registry = new TaskExecutionRegistry();
        UUID taskId = UUID.randomUUID();
        RunningTaskHandle old = new RunningTaskHandle(taskId, UUID.randomUUID(), Thread.currentThread(), repository);
        RunningTaskHandle current = new RunningTaskHandle(taskId, UUID.randomUUID(), Thread.currentThread(), repository);
        registry.register(current);
        registry.remove(old);
        assertThat(registry.find(taskId)).contains(current);
        registry.remove(current);
        assertThat(registry.find(taskId)).isEmpty();
    }

    @Test
    void registersCancelsAndRemovesRunningTask() {
        TaskRuntimeHandleRepository repository = org.mockito.Mockito.mock(TaskRuntimeHandleRepository.class);
        TaskExecutionRegistry registry = new TaskExecutionRegistry();
        UUID taskId = UUID.randomUUID();
        UUID runtimeHandleId = UUID.randomUUID();
        RunningTaskHandle handle = new RunningTaskHandle(taskId, runtimeHandleId, Thread.currentThread(), repository);

        registry.register(handle);

        assertThat(registry.find(taskId)).contains(handle);
        assertThat(registry.activeCount()).isEqualTo(1);
        assertThat(registry.runningTaskIds()).containsExactly(taskId);
        assertThat(registry.cancel(taskId)).isTrue();
        assertThat(handle.isCancellationRequested()).isTrue();
        verify(repository).markCancelling(runtimeHandleId);

        registry.remove(taskId);
        assertThat(registry.find(taskId)).isEmpty();
        assertThat(registry.activeCount()).isZero();
    }

    @Test
    void rejectsDuplicateRegistrationAndMissingCancelIsNoop() {
        TaskRuntimeHandleRepository repository = org.mockito.Mockito.mock(TaskRuntimeHandleRepository.class);
        TaskExecutionRegistry registry = new TaskExecutionRegistry();
        UUID taskId = UUID.randomUUID();

        registry.register(new RunningTaskHandle(taskId, UUID.randomUUID(), Thread.currentThread(), repository));

        assertThatThrownBy(() -> registry.register(new RunningTaskHandle(taskId, UUID.randomUUID(), Thread.currentThread(), repository)))
                .isInstanceOf(IllegalStateException.class);
        assertThat(registry.cancel(UUID.randomUUID())).isFalse();
    }

    @Test
    void marksRuntimeHandleTerminalStates() {
        TaskRuntimeHandleRepository repository = org.mockito.Mockito.mock(TaskRuntimeHandleRepository.class);
        UUID runtimeHandleId = UUID.randomUUID();
        RunningTaskHandle handle = new RunningTaskHandle(UUID.randomUUID(), runtimeHandleId, Thread.currentThread(), repository);

        handle.markTerminated(TaskRuntimeHandleStatus.CANCELLED);
        handle.markError(TaskRuntimeHandleStatus.CANCEL_FAILED, "CANCEL_FAILED", "失败");

        verify(repository).markTerminated(runtimeHandleId, TaskRuntimeHandleStatus.CANCELLED);
        verify(repository).markError(runtimeHandleId, TaskRuntimeHandleStatus.CANCEL_FAILED, "CANCEL_FAILED", "失败");
    }

    @Test
    void runningHandleRegistersProcessesAndExposesIdentifiers() {
        TaskRuntimeHandleRepository repository = org.mockito.Mockito.mock(TaskRuntimeHandleRepository.class);
        Thread owner = org.mockito.Mockito.mock(Thread.class);
        Process process = org.mockito.Mockito.mock(Process.class);
        UUID taskId = UUID.randomUUID();
        UUID runtimeHandleId = UUID.randomUUID();
        UUID environmentId = UUID.randomUUID();
        when(process.pid()).thenReturn(1234L);
        RunningTaskHandle handle = new RunningTaskHandle(taskId, runtimeHandleId, owner, repository);

        handle.registerLocalProcess(null, Duration.ofSeconds(1));
        handle.registerLocalProcess(process, Duration.ofSeconds(1));
        handle.registerRemoteProcess(environmentId, 10L, 11L, "marker");

        assertThat(handle.taskId()).isEqualTo(taskId);
        assertThat(handle.runtimeHandleId()).isEqualTo(runtimeHandleId);
        verify(repository).registerLocalProcess(runtimeHandleId, 1234L);
        verify(repository).registerRemoteProcess(runtimeHandleId, environmentId, 10L, 11L, "marker");
    }

    @Test
    void cancellationIsIdempotentAndCancelsResourcesAddedBeforeAndAfterRequest() {
        TaskRuntimeHandleRepository repository = org.mockito.Mockito.mock(TaskRuntimeHandleRepository.class);
        Thread owner = org.mockito.Mockito.mock(Thread.class);
        CancellableResource early = org.mockito.Mockito.mock(CancellableResource.class);
        CancellableResource late = org.mockito.Mockito.mock(CancellableResource.class);
        UUID runtimeHandleId = UUID.randomUUID();
        RunningTaskHandle handle = new RunningTaskHandle(UUID.randomUUID(), runtimeHandleId, owner, repository);

        handle.addResource(null);
        handle.addResource(early);
        handle.requestCancel();
        handle.requestCancel();
        handle.addResource(late);

        assertThat(handle.isCancellationRequested()).isTrue();
        verify(repository, times(1)).markCancelling(runtimeHandleId);
        verify(early, times(1)).cancel();
        verify(late, times(1)).cancel();
        verify(owner, times(1)).interrupt();
    }

    @Test
    void throwIfCancellationRequestedAlsoHonorsCurrentThreadInterrupt() {
        TaskRuntimeHandleRepository repository = org.mockito.Mockito.mock(TaskRuntimeHandleRepository.class);
        Thread owner = org.mockito.Mockito.mock(Thread.class);
        RunningTaskHandle handle = new RunningTaskHandle(UUID.randomUUID(), UUID.randomUUID(), owner, repository);

        try {
            Thread.currentThread().interrupt();
            assertThatThrownBy(handle::throwIfCancellationRequested).isInstanceOf(TaskCancelledException.class);
            verify(repository, never()).markCancelling(org.mockito.ArgumentMatchers.any());
        } finally {
            Thread.interrupted();
        }
    }
}
