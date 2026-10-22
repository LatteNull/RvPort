package cn.rvport.backend.task;

import cn.rvport.backend.project.ProjectAccessService;
import cn.rvport.backend.security.RvPortUserPrincipal;
import java.util.UUID;
import org.springframework.http.MediaType;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

@RestController
public class TaskLogNotificationController {

    private final ProjectAccessService projectAccessService;
    private final TaskLogNotificationBroker broker;

    public TaskLogNotificationController(ProjectAccessService projectAccessService, TaskLogNotificationBroker broker) {
        this.projectAccessService = projectAccessService;
        this.broker = broker;
    }

    @GetMapping(path = "/api/tasks/{taskId}/log-notifications", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter notifications(
            @AuthenticationPrincipal RvPortUserPrincipal principal,
            @PathVariable UUID taskId,
            @RequestParam(required = false) String afterEventId
    ) {
        TaskView task = projectAccessService.requireTaskAccess(taskId, principal.id(), principal.superAdmin());
        return broker.subscribe(task, TaskLogIncrementRequest.parseCursor(afterEventId));
    }
}
