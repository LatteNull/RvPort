package cn.rvport.backend.worker;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.task.TaskDispatchService;
import cn.rvport.backend.task.TaskRepository;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.task.TaskView;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

class TaskDispatchRepairerTests {

    @Test
    void republishesEveryPendingTaskAndContinuesAfterIndividualFailure() {
        TaskRepository repository = Mockito.mock(TaskRepository.class);
        TaskDispatchService dispatchService = Mockito.mock(TaskDispatchService.class);
        TaskView first = task();
        TaskView second = task();
        when(repository.findPendingBefore(any(OffsetDateTime.class), eq(50))).thenReturn(List.of(first, second));
        Mockito.doThrow(new IllegalStateException("queue down"))
                .when(dispatchService).publishAndMarkQueued(first);

        new TaskDispatchRepairer(repository, dispatchService).repairPendingDispatch();

        verify(dispatchService).publishAndMarkQueued(first);
        verify(dispatchService).publishAndMarkQueued(second);
    }

    @Test
    void emptyPendingListIsANoop() {
        TaskRepository repository = Mockito.mock(TaskRepository.class);
        TaskDispatchService dispatchService = Mockito.mock(TaskDispatchService.class);
        when(repository.findPendingBefore(any(OffsetDateTime.class), eq(50))).thenReturn(List.of());

        new TaskDispatchRepairer(repository, dispatchService).repairPendingDispatch();

        Mockito.verifyNoInteractions(dispatchService);
    }

    private static TaskView task() {
        OffsetDateTime now = OffsetDateTime.now();
        return new TaskView(UUID.randomUUID(), UUID.randomUUID(), "TEST", TaskStatus.PENDING, 0, "pending",
                UUID.randomUUID(), now, null, null, null, 60, null, null, 0);
    }
}
