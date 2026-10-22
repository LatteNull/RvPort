package cn.rvport.backend.worker;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.config.WorkerProperties;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

@Service
public class WorkerManagementService {

    private final WorkerProperties properties;
    private final WorkerInstanceRepository workerInstanceRepository;
    private final WorkerTaskRepository workerTaskRepository;

    public WorkerManagementService(
            WorkerProperties properties,
            WorkerInstanceRepository workerInstanceRepository,
            WorkerTaskRepository workerTaskRepository
    ) {
        this.properties = properties;
        this.workerInstanceRepository = workerInstanceRepository;
        this.workerTaskRepository = workerTaskRepository;
    }

    public PageResponse<WorkerInstanceResponse> list(WorkerInstanceListRequest request) {
        validateQuery(request);
        PageResponse<WorkerInstanceView> page = workerInstanceRepository.list(request, properties.offlineTimeoutSeconds());
        List<WorkerInstanceResponse> items = page.items().stream()
                .map(WorkerInstanceResponse::from)
                .toList();
        return PageResponse.of(items, page.page(), page.pageSize(), page.total());
    }

    public WorkerInstanceDetailResponse get(String workerInstanceId) {
        WorkerInstanceView worker = workerInstanceRepository
                .findByInstanceId(workerInstanceId, properties.offlineTimeoutSeconds())
                .orElseThrow(() -> notFound(workerInstanceId));
        return new WorkerInstanceDetailResponse(
                WorkerInstanceResponse.from(worker),
                workerTaskRepository.findRunningTasks(worker.instanceId())
        );
    }

    public WorkerInstanceResponse updateConcurrency(String workerInstanceId, UpdateWorkerConcurrencyRequest request) {
        if (request.concurrencyLimit() == null) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "WORKER_CONCURRENCY_INVALID", "并发限制不能为空");
        }
        int maxConcurrencyLimit = properties.maxConcurrencyLimit();
        if (request.concurrencyLimit() > maxConcurrencyLimit) {
            throw new ApiException(
                    HttpStatus.BAD_REQUEST,
                    "WORKER_CONCURRENCY_INVALID",
                    "并发限制不能超过 " + maxConcurrencyLimit
            );
        }
        WorkerInstanceView existing = workerInstanceRepository
                .findByInstanceId(workerInstanceId, properties.offlineTimeoutSeconds())
                .orElseThrow(() -> notFound(workerInstanceId));
        WorkerInstanceView updated = workerInstanceRepository.updateConcurrencyLimit(
                existing.instanceId(),
                request.concurrencyLimit(),
                properties.offlineTimeoutSeconds()
        );
        return WorkerInstanceResponse.from(updated);
    }

    private void validateQuery(WorkerInstanceListRequest request) {
        if (notBlank(request.sortDirection())
                && !"asc".equalsIgnoreCase(request.sortDirection())
                && !"desc".equalsIgnoreCase(request.sortDirection())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "WORKER_QUERY_INVALID", "排序方向只支持 asc 或 desc");
        }
        if (notBlank(request.sortBy())
                && !List.of(
                        "instanceId",
                        "hostname",
                        "status",
                        "concurrencyLimit",
                        "activeConcurrency",
                        "activeTaskCount",
                        "startedAt",
                        "updatedAt",
                        "lastHeartbeatAt"
                ).contains(request.sortBy().trim())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "WORKER_QUERY_INVALID", "不支持的排序字段");
        }
    }

    private ApiException notFound(String workerInstanceId) {
        return new ApiException(HttpStatus.NOT_FOUND, "WORKER_NOT_FOUND", "Worker 不存在: " + workerInstanceId);
    }

    private boolean notBlank(String value) {
        return value != null && !value.isBlank();
    }
}
