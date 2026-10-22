package cn.rvport.backend.worker;

import cn.rvport.backend.common.web.ApiResponse;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.common.web.TraceIdFilter;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
@Validated
public class AdminWorkerController {

    private final WorkerManagementService workerManagementService;

    public AdminWorkerController(WorkerManagementService workerManagementService) {
        this.workerManagementService = workerManagementService;
    }

    @GetMapping("/api/admin/workers")
    public ApiResponse<PageResponse<WorkerInstanceResponse>> list(
            @Valid @ModelAttribute WorkerInstanceListRequest query,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(workerManagementService.list(query), TraceIdFilter.currentTraceId(request));
    }

    @GetMapping("/api/admin/workers/{workerInstanceId}")
    public ApiResponse<WorkerInstanceDetailResponse> get(
            @PathVariable String workerInstanceId,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(workerManagementService.get(workerInstanceId), TraceIdFilter.currentTraceId(request));
    }

    @PutMapping("/api/admin/workers/{workerInstanceId}/concurrency")
    public ApiResponse<WorkerInstanceResponse> updateConcurrency(
            @PathVariable String workerInstanceId,
            @Valid @RequestBody UpdateWorkerConcurrencyRequest body,
            HttpServletRequest request
    ) {
        return ApiResponse.ok(
                workerManagementService.updateConcurrency(workerInstanceId, body),
                TraceIdFilter.currentTraceId(request)
        );
    }
}
