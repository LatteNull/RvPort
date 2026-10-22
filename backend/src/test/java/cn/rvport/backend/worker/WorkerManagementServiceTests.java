package cn.rvport.backend.worker;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.config.RvPortAppMode;
import cn.rvport.backend.config.WorkerProperties;
import cn.rvport.backend.task.TaskStatus;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class WorkerManagementServiceTests {

    private final WorkerInstanceRepository workerRepository = org.mockito.Mockito.mock(WorkerInstanceRepository.class);
    private final WorkerTaskRepository taskRepository = org.mockito.Mockito.mock(WorkerTaskRepository.class);
    private final WorkerManagementService service = new WorkerManagementService(properties(), workerRepository, taskRepository);

    @Test
    void listsWorkersWithPagingAndFiltering() {
        WorkerInstanceListRequest request = new WorkerInstanceListRequest(1, 20, WorkerInstanceStatus.ONLINE, "worker", null, true, "lastHeartbeatAt", "desc");
        when(workerRepository.list(request, 60)).thenReturn(PageResponse.of(List.of(worker("worker-1", 2)), 1, 20, 1));

        PageResponse<WorkerInstanceResponse> page = service.list(request);

        assertThat(page.items()).hasSize(1);
        assertThat(page.items().getFirst().instanceId()).isEqualTo("worker-1");
        assertThat(page.items().getFirst().activeTaskCount()).isEqualTo(2);
    }

    @Test
    void rejectsUnsupportedSortDirectionAndSortField() {
        assertThatThrownBy(() -> service.list(new WorkerInstanceListRequest(1, 20, null, null, null, null, "lastHeartbeatAt", "sideways")))
                .isInstanceOf(ApiException.class)
                .extracting("code")
                .isEqualTo("WORKER_QUERY_INVALID");

        assertThatThrownBy(() -> service.list(new WorkerInstanceListRequest(1, 20, null, null, null, null, "prefetchCount", "asc")))
                .isInstanceOf(ApiException.class)
                .extracting("code")
                .isEqualTo("WORKER_QUERY_INVALID");
    }

    @Test
    void returnsWorkerDetailsWithRunningTasks() {
        WorkerInstanceView worker = worker("worker-1", 1);
        WorkerTaskResponse task = new WorkerTaskResponse(
                UUID.randomUUID(),
                UUID.randomUUID(),
                "demo",
                "BUILD_VALIDATION",
                TaskStatus.RUNNING,
                40,
                "building",
                OffsetDateTime.now()
        );
        when(workerRepository.findByInstanceId("worker-1", 60)).thenReturn(Optional.of(worker));
        when(taskRepository.findRunningTasks("worker-1")).thenReturn(List.of(task));

        WorkerInstanceDetailResponse detail = service.get("worker-1");

        assertThat(detail.worker().instanceId()).isEqualTo("worker-1");
        assertThat(detail.runningTasks()).containsExactly(task);
    }

    @Test
    void updatesConcurrencyWithinBoundsAndRejectsMissingOrTooLargeValues() {
        WorkerInstanceView worker = worker("worker-1", 0);
        when(workerRepository.findByInstanceId("worker-1", 60)).thenReturn(Optional.of(worker));
        when(workerRepository.updateConcurrencyLimit("worker-1", 4, 60)).thenReturn(worker("worker-1", 0, 4));

        WorkerInstanceResponse updated = service.updateConcurrency("worker-1", new UpdateWorkerConcurrencyRequest(4));

        assertThat(updated.concurrencyLimit()).isEqualTo(4);
        verify(workerRepository).updateConcurrencyLimit("worker-1", 4, 60);

        assertThatThrownBy(() -> service.updateConcurrency("worker-1", new UpdateWorkerConcurrencyRequest(null)))
                .isInstanceOf(ApiException.class)
                .extracting("code")
                .isEqualTo("WORKER_CONCURRENCY_INVALID");
        assertThatThrownBy(() -> service.updateConcurrency("worker-1", new UpdateWorkerConcurrencyRequest(9)))
                .isInstanceOf(ApiException.class)
                .extracting("code")
                .isEqualTo("WORKER_CONCURRENCY_INVALID");
    }

    @Test
    void missingWorkerReturnsNotFoundWithoutLeakingTaskDetails() {
        when(workerRepository.findByInstanceId("missing", 60)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.get("missing"))
                .isInstanceOf(ApiException.class)
                .extracting("code")
                .isEqualTo("WORKER_NOT_FOUND");
    }

    @Test
    void acceptsBlankSortOptionsAndCaseInsensitiveAscendingDirection() {
        WorkerInstanceListRequest blank = new WorkerInstanceListRequest(1, 20, null, null, null, null, " ", " ");
        WorkerInstanceListRequest ascending = new WorkerInstanceListRequest(1, 20, null, null, null, null, "instanceId", "ASC");
        when(workerRepository.list(blank, 60)).thenReturn(PageResponse.of(List.of(), 1, 20, 0));
        when(workerRepository.list(ascending, 60)).thenReturn(PageResponse.of(List.of(), 1, 20, 0));

        assertThat(service.list(blank).items()).isEmpty();
        assertThat(service.list(ascending).items()).isEmpty();
    }

    @Test
    void rejectsConcurrencyUpdateForMissingWorker() {
        when(workerRepository.findByInstanceId("missing", 60)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.updateConcurrency("missing", new UpdateWorkerConcurrencyRequest(2)))
                .isInstanceOf(ApiException.class)
                .extracting("code").isEqualTo("WORKER_NOT_FOUND");
    }

    private WorkerInstanceView worker(String instanceId, int activeTaskCount) {
        return worker(instanceId, activeTaskCount, 1);
    }

    private WorkerInstanceView worker(String instanceId, int activeTaskCount, int concurrencyLimit) {
        OffsetDateTime now = OffsetDateTime.now();
        return new WorkerInstanceView(
                instanceId,
                "host",
                100L,
                "dev",
                WorkerInstanceStatus.ONLINE,
                concurrencyLimit,
                concurrencyLimit,
                activeTaskCount,
                now.minusMinutes(1),
                now,
                now.minusMinutes(1),
                now
        );
    }

    private WorkerProperties properties() {
        return new WorkerProperties(true, "test-worker", RvPortAppMode.COMBINED, 1, 8, 10, 60);
    }
}
