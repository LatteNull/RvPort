package cn.rvport.backend.task;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.audit.AuditLogService;
import cn.rvport.backend.project.ProjectAccessService;
import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.user.UserStatus;
import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.mock.web.MockHttpServletRequest;

class TaskControllerTests {

    @Test
    void delegatesQueriesCancellationAndLogReads() {
        TaskService taskService = mock(TaskService.class);
        TaskLogService logService = mock(TaskLogService.class);
        TaskLogIncrementService incrementService = mock(TaskLogIncrementService.class);
        AuditLogService auditService = mock(AuditLogService.class);
        ProjectAccessService accessService = mock(ProjectAccessService.class);
        TaskController controller = new TaskController(taskService, logService, incrementService, auditService, accessService);
        RvPortUserPrincipal principal = principal();
        UUID projectId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        MockHttpServletRequest request = new MockHttpServletRequest();
        TaskResponse cancelled = response(taskId, projectId, TaskStatus.CANCELLED);
        when(taskService.cancel(taskId, principal.id(), false)).thenReturn(cancelled);

        assertThat(controller.listProjectTasks(principal, projectId, null, request).timestamp()).isNotNull();
        assertThat(controller.get(principal, taskId, request).timestamp()).isNotNull();
        assertThat(controller.cancel(principal, taskId, request).data()).isSameAs(cancelled);
        assertThat(controller.logs(principal, taskId, TaskLogType.STDOUT, 2, 50, request).timestamp()).isNotNull();
        assertThat(controller.logIncrements(principal, taskId, "7", "20", request).timestamp()).isNotNull();
        assertThat(controller.logContent(principal, taskId, "merged,stderr", 100,
                1L, 2L, 3L, 10, 20, 30, request).timestamp()).isNotNull();

        verify(accessService, org.mockito.Mockito.times(3)).requireTaskAccess(taskId, principal.id(), false);
        verify(incrementService).read(taskId, new TaskLogIncrementRequest(7, 20));
        verify(logService).content(eq(taskId), any(TaskLogContentRequest.class));
        verify(auditService).record(eq(principal.id()), eq("task.cancel"), eq("task"), eq(taskId), any(), eq(request));
    }

    @Test
    void downloadChecksExactTaskLogPairAndBuildsAttachment() {
        TaskService taskService = mock(TaskService.class);
        TaskLogService logService = mock(TaskLogService.class);
        ProjectAccessService accessService = mock(ProjectAccessService.class);
        TaskController controller = new TaskController(taskService, logService, mock(TaskLogIncrementService.class),
                mock(AuditLogService.class), accessService);
        RvPortUserPrincipal principal = principal();
        UUID taskId = UUID.randomUUID();
        UUID logId = UUID.randomUUID();
        ByteArrayResource resource = new ByteArrayResource("log".getBytes(StandardCharsets.UTF_8));
        when(logService.download(taskId, logId)).thenReturn(
                new TaskLogService.DownloadableTaskLog(resource, "task.log", "text/plain"));

        var response = controller.downloadLog(principal, taskId, logId);

        assertThat(response.getBody()).isSameAs(resource);
        assertThat(response.getHeaders().getContentDisposition().getFilename()).isEqualTo("task.log");
        verify(accessService).requireTaskLogAccess(taskId, logId, principal.id(), false);
    }

    private TaskResponse response(UUID taskId, UUID projectId, TaskStatus status) {
        return new TaskResponse(taskId, projectId, RvPortTaskTypes.KB_SCAN, status, 100, "done",
                OffsetDateTime.now(), OffsetDateTime.now(), OffsetDateTime.now(), OffsetDateTime.now(),
                null, null, Map.of());
    }

    private RvPortUserPrincipal principal() {
        return new RvPortUserPrincipal(UUID.randomUUID(), "user", "User", "user@example.com",
                false, false, UserStatus.ACTIVE);
    }
}
