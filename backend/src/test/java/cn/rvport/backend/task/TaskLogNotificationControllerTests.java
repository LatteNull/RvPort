package cn.rvport.backend.task;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.common.error.GlobalExceptionHandler;
import cn.rvport.backend.project.ProjectAccessService;
import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.user.UserStatus;
import java.time.OffsetDateTime;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.core.MethodParameter;
import org.springframework.http.HttpStatus;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.bind.support.WebDataBinderFactory;
import org.springframework.web.context.request.NativeWebRequest;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.method.support.ModelAndViewContainer;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

class TaskLogNotificationControllerTests {

    private final ProjectAccessService projectAccessService = org.mockito.Mockito.mock(ProjectAccessService.class);
    private final TaskLogNotificationBroker broker = org.mockito.Mockito.mock(TaskLogNotificationBroker.class);
    private final MockMvc mockMvc = MockMvcBuilders
            .standaloneSetup(new TaskLogNotificationController(projectAccessService, broker))
            .setCustomArgumentResolvers(new PrincipalArgumentResolver())
            .setControllerAdvice(new GlobalExceptionHandler())
            .build();

    @Test
    void subscribesAfterAccessGuardWithConsumedCursor() throws Exception {
        UUID taskId = UUID.randomUUID();
        TaskView task = task(taskId);
        when(projectAccessService.requireTaskAccess(eq(taskId), any(), eq(false))).thenReturn(task);
        when(broker.subscribe(task, 12)).thenReturn(new SseEmitter());

        MvcResult result = mockMvc.perform(get("/api/tasks/{taskId}/log-notifications", taskId)
                        .param("afterEventId", "12"))
                .andReturn();

        assertThat(result.getResponse().getStatus()).isBetween(200, 299);
        verify(broker).subscribe(task, 12);
    }

    @Test
    void rejectsInvalidCursorBeforeSubscription() throws Exception {
        UUID taskId = UUID.randomUUID();
        when(projectAccessService.requireTaskAccess(eq(taskId), any(), eq(false))).thenReturn(task(taskId));

        MvcResult result = mockMvc.perform(get("/api/tasks/{taskId}/log-notifications", taskId)
                        .param("afterEventId", "bad"))
                .andReturn();

        assertThat(result.getResponse().getStatus()).isEqualTo(400);
        assertThat(result.getResponse().getContentAsString()).contains("TASK_LOG_EVENT_CURSOR_INVALID");
        verify(broker, never()).subscribe(any(), any(Long.class));
    }

    @Test
    void rejectsUnauthorizedBeforeParsingOrSubscription() throws Exception {
        UUID taskId = UUID.randomUUID();
        doThrow(new ApiException(HttpStatus.NOT_FOUND, "TASK_NOT_FOUND", "任务不存在"))
                .when(projectAccessService).requireTaskAccess(eq(taskId), any(), anyBoolean());

        MvcResult result = mockMvc.perform(get("/api/tasks/{taskId}/log-notifications", taskId)
                        .param("afterEventId", "bad"))
                .andReturn();

        assertThat(result.getResponse().getStatus()).isEqualTo(404);
        assertThat(result.getResponse().getContentAsString()).contains("TASK_NOT_FOUND");
        verify(broker, never()).subscribe(any(), any(Long.class));
    }

    private TaskView task(UUID taskId) {
        OffsetDateTime now = OffsetDateTime.now();
        return new TaskView(taskId, UUID.randomUUID(), RvPortTaskTypes.ENV_RUN_SCRIPT, TaskStatus.RUNNING, 10,
                "running", UUID.randomUUID(), now, now, now, null, null, null, null, 0);
    }

    private static final class PrincipalArgumentResolver implements HandlerMethodArgumentResolver {
        @Override
        public boolean supportsParameter(MethodParameter parameter) {
            return parameter.hasParameterAnnotation(org.springframework.security.core.annotation.AuthenticationPrincipal.class);
        }

        @Override
        public Object resolveArgument(MethodParameter parameter, ModelAndViewContainer mavContainer,
                                      NativeWebRequest webRequest, WebDataBinderFactory binderFactory) {
            return new RvPortUserPrincipal(UUID.randomUUID(), "user", "User", null, false, false, UserStatus.ACTIVE);
        }
    }
}
