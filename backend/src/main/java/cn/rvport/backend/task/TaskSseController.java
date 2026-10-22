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
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

@RestController
public class TaskSseController {

    private final TaskEventService taskEventService;
    private final TaskSseBroker taskSseBroker;
    private final ProjectAccessService projectAccessService;

    public TaskSseController(TaskEventService taskEventService, TaskSseBroker taskSseBroker, ProjectAccessService projectAccessService) {
        this.taskEventService = taskEventService;
        this.taskSseBroker = taskSseBroker;
        this.projectAccessService = projectAccessService;
    }

    @GetMapping(path = "/api/projects/{projectId}/task-events", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter events(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID projectId,
            @RequestParam(name = "afterEventId", required = false) String afterEventId,
            @RequestHeader(name = "Last-Event-ID", required = false) String lastEventId
    ) {
        Long explicitCursor = parseCursor(afterEventId, "afterEventId");
        Long resumeCursor = explicitCursor == null ? parseCursor(lastEventId, "Last-Event-ID") : null;
        projectAccessService.requireProjectAccess(projectId, principal.id(), principal.superAdmin());
        long cursor = explicitCursor != null
                ? explicitCursor
                : resumeCursor != null ? resumeCursor : taskEventService.latestEventId(projectId);
        SseEmitter emitter = taskSseBroker.subscribe(projectId);
        try {
            for (TaskEventView event : taskEventService.listAfter(projectId, cursor, 500)) {
                emitter.send(taskSseBroker.toSseEvent(event));
            }
        } catch (IOException | IllegalStateException ex) {
            emitter.completeWithError(ex);
        }
        return emitter;
    }

    private Long parseCursor(String value, String fieldName) {
        if (value == null || value.isBlank()) {
            return null;
        }
        try {
            long parsed = Long.parseLong(value.trim());
            if (parsed < 0) {
                throw invalidCursor(fieldName);
            }
            return parsed;
        } catch (NumberFormatException ex) {
            throw invalidCursor(fieldName);
        }
    }

    private ApiException invalidCursor(String fieldName) {
        return new ApiException(HttpStatus.BAD_REQUEST, "SSE_LAST_EVENT_ID_INVALID", fieldName + " 必须是任务事件非负数字 ID");
    }
}
