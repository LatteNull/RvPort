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
import java.util.List;
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

class TaskLogSseControllerTests {

    private final TaskLogEventService taskLogEventService = org.mockito.Mockito.mock(TaskLogEventService.class);
    private final TaskLogSseBroker taskLogSseBroker = org.mockito.Mockito.mock(TaskLogSseBroker.class);
    private final ProjectAccessService projectAccessService = org.mockito.Mockito.mock(ProjectAccessService.class);
    private final TaskRepository taskRepository = org.mockito.Mockito.mock(TaskRepository.class);
    private final MockMvc mockMvc = MockMvcBuilders
            .standaloneSetup(new TaskLogSseController(taskLogEventService, taskLogSseBroker, projectAccessService, taskRepository))
            .setCustomArgumentResolvers(new PrincipalArgumentResolver())
            .setControllerAdvice(new GlobalExceptionHandler())
            .build();

    @Test
    void replaysLogEventsAfterCursor() throws Exception {
        UUID taskId = UUID.randomUUID();
        TaskView task = task(taskId, TaskStatus.RUNNING);
        SseEmitter emitter = new SseEmitter();
        when(projectAccessService.requireTaskAccess(eq(taskId), any(), eq(false))).thenReturn(task);
        when(taskLogSseBroker.subscribe(taskId)).thenReturn(emitter);
        when(taskLogEventService.listAfter(taskId, 7L, 1000)).thenReturn(List.of());
        when(taskRepository.findById(taskId)).thenReturn(java.util.Optional.of(task));

        MvcResult result = mockMvc.perform(get("/api/tasks/{taskId}/log-events", taskId)
                        .header("Last-Event-ID", "7"))
                .andReturn();

        assertThat(result.getResponse().getStatus()).isBetween(200, 299);
        verify(taskLogEventService).listAfter(taskId, 7L, 1000);
    }

    @Test
    void rejectsInvalidCursorAndUnauthorizedBeforeSubscribe() throws Exception {
        UUID taskId = UUID.randomUUID();

        MvcResult invalid = mockMvc.perform(get("/api/tasks/{taskId}/log-events", taskId)
                        .header("Last-Event-ID", "-1"))
                .andReturn();
        assertThat(invalid.getResponse().getStatus()).isEqualTo(400);

        doThrow(new ApiException(HttpStatus.NOT_FOUND, "TASK_NOT_FOUND", "任务不存在"))
                .when(projectAccessService).requireTaskAccess(eq(taskId), any(), anyBoolean());
        MvcResult unauthorized = mockMvc.perform(get("/api/tasks/{taskId}/log-events", taskId))
                .andReturn();
        assertThat(unauthorized.getResponse().getStatus()).isEqualTo(404);
        verify(taskLogSseBroker, never()).subscribe(taskId);
    }

    private TaskView task(UUID taskId, TaskStatus status) {
        return new TaskView(
                taskId,
                UUID.randomUUID(),
                RvPortTaskTypes.ENV_RUN_SCRIPT,
                status,
                status == TaskStatus.SUCCEEDED ? 100 : 10,
                "message",
                UUID.randomUUID(),
                OffsetDateTime.now(),
                OffsetDateTime.now(),
                OffsetDateTime.now(),
                status == TaskStatus.RUNNING ? null : OffsetDateTime.now(),
                30,
                null,
                null,
                0
        );
    }

    private static final class PrincipalArgumentResolver implements HandlerMethodArgumentResolver {

        @Override
        public boolean supportsParameter(MethodParameter parameter) {
            return parameter.hasParameterAnnotation(org.springframework.security.core.annotation.AuthenticationPrincipal.class);
        }

        @Override
        public Object resolveArgument(
                MethodParameter parameter,
                ModelAndViewContainer mavContainer,
                NativeWebRequest webRequest,
                WebDataBinderFactory binderFactory
        ) {
            return new RvPortUserPrincipal(
                    UUID.randomUUID(),
                    "user",
                    "User",
                    null,
                    false,
                    false,
                    UserStatus.ACTIVE
            );
        }
    }
}
