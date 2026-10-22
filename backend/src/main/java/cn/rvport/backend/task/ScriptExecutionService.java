package cn.rvport.backend.task;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.project.ProjectAccessService;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ScriptExecutionService {

    private final ScriptExecutionRepository repository;
    private final ProjectAccessService projectAccessService;
    private final ObjectMapper objectMapper;

    public ScriptExecutionService(
            ScriptExecutionRepository repository,
            ProjectAccessService projectAccessService,
            ObjectMapper objectMapper
    ) {
        this.repository = repository;
        this.projectAccessService = projectAccessService;
        this.objectMapper = objectMapper;
    }

    @Transactional(readOnly = true)
    public PageResponse<ScriptExecutionResponse> list(
            UUID projectId,
            ScriptExecutionListRequest request,
            UUID actorUserId,
            boolean superAdmin
    ) {
        projectAccessService.requireProjectAccess(projectId, actorUserId, superAdmin);
        long total = repository.count(projectId, request);
        List<ScriptExecutionResponse> items = repository.list(projectId, request).stream()
                .map(this::toResponse)
                .toList();
        return PageResponse.of(items, request.normalizedPage(), request.normalizedPageSize(), total);
    }

    @Transactional(readOnly = true)
    public ScriptExecutionDetailResponse get(UUID taskId, UUID actorUserId, boolean superAdmin) {
        projectAccessService.requireTaskAccess(taskId, actorUserId, superAdmin);
        ScriptExecutionRepository.DetailRow detail = repository.findDetail(taskId)
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "SCRIPT_EXECUTION_NOT_FOUND", "脚本执行记录不存在"));
        ScriptExecutionRepository.Row row = detail.row();
        return new ScriptExecutionDetailResponse(
                row.taskId(),
                row.taskId(),
                row.projectId(),
                row.environmentId(),
                row.environmentName(),
                ScriptExecutionStatus.fromTaskStatus(row.taskStatus()),
                row.taskStatus(),
                row.progress(),
                row.message(),
                row.scriptSha256(),
                row.scriptLength(),
                detail.toolRunId(),
                detail.toolName(),
                row.exitCode(),
                safeSummary(detail.summary() == null ? null : detail.summary().data()),
                row.logEventCount(),
                row.createdAt(),
                row.startedAt(),
                row.finishedAt()
        );
    }

    private ScriptExecutionResponse toResponse(ScriptExecutionRepository.Row row) {
        return new ScriptExecutionResponse(
                row.taskId(),
                row.taskId(),
                row.projectId(),
                row.environmentId(),
                row.environmentName(),
                ScriptExecutionStatus.fromTaskStatus(row.taskStatus()),
                row.taskStatus(),
                row.progress(),
                row.message(),
                row.scriptSha256(),
                row.scriptLength(),
                row.exitCode(),
                row.logEventCount(),
                row.createdAt(),
                row.startedAt(),
                row.finishedAt()
        );
    }

    private Map<String, Object> safeSummary(String json) {
        if (json == null || json.isBlank()) {
            return Map.of();
        }
        try {
            Map<String, Object> summary = objectMapper.readValue(json, new TypeReference<>() {
            });
            summary.remove("script");
            summary.remove("password");
            summary.remove("privateKey");
            summary.remove("passphrase");
            summary.remove("secret");
            return summary;
        } catch (IOException ex) {
            return Map.of();
        }
    }
}
