package cn.rvport.backend.task;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.project.ProjectAccessService;
import cn.rvport.backend.security.RvPortUserPrincipal;
import java.io.IOException;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

@RestController
public class TaskLogSseController {

    private final TaskLogEventService taskLogEventService;
    private final TaskLogSseBroker taskLogSseBroker;
    private final ProjectAccessService projectAccessService;
    private final TaskRepository taskRepository;

    public TaskLogSseController(
            TaskLogEventService taskLogEventService,
            TaskLogSseBroker taskLogSseBroker,
            ProjectAccessService projectAccessService,
            TaskRepository taskRepository
    ) {
        this.taskLogEventService = taskLogEventService;
        this.taskLogSseBroker = taskLogSseBroker;
        this.projectAccessService = projectAccessService;
        this.taskRepository = taskRepository;
    }

    @Deprecated(since = "0.0.2", forRemoval = false)
    @GetMapping(path = "/api/tasks/{taskId}/log-events", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter logEvents(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID taskId,
            @RequestHeader(name = "Last-Event-ID", required = false) String lastEventId
    ) {
        long cursor = parseLastEventId(lastEventId);
        TaskView task = projectAccessService.requireTaskAccess(taskId, principal.id(), principal.superAdmin());
        SseEmitter emitter = taskLogSseBroker.subscribe(taskId);
        try {
            for (TaskLogEventView event : taskLogEventService.listAfter(taskId, cursor, 1000)) {
                emitter.send(taskLogSseBroker.toSseEvent(event));
            }
            TaskView latest = taskRepository.findById(taskId).orElse(task);
            if (taskRepository.isTerminal(latest.status())) {
                emitter.send(taskLogSseBroker.toTerminalEvent(latest));
                emitter.complete();
            }
        } catch (IOException | IllegalStateException ex) {
            emitter.completeWithError(ex);
        }
        return emitter;
    }

    private long parseLastEventId(String lastEventId) {
        if (lastEventId == null || lastEventId.isBlank()) {
            return 0L;
        }
        try {
            long value = Long.parseLong(lastEventId.trim());
            if (value < 0) {
                throw new NumberFormatException("negative");
            }
            return value;
        } catch (NumberFormatException ex) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "SSE_LAST_EVENT_ID_INVALID", "Last-Event-ID 必须是日志事件数字 ID");
        }
    }
}
