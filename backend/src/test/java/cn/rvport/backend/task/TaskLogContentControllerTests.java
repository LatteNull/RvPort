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

import cn.rvport.backend.audit.AuditLogService;
import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.common.error.GlobalExceptionHandler;
import cn.rvport.backend.project.ProjectAccessService;
import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.user.UserStatus;
import java.util.Map;
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

class TaskLogContentControllerTests {

    private final TaskService taskService = org.mockito.Mockito.mock(TaskService.class);
    private final TaskLogService taskLogService = org.mockito.Mockito.mock(TaskLogService.class);
    private final TaskLogIncrementService taskLogIncrementService = org.mockito.Mockito.mock(TaskLogIncrementService.class);
    private final AuditLogService auditLogService = org.mockito.Mockito.mock(AuditLogService.class);
    private final ProjectAccessService projectAccessService = org.mockito.Mockito.mock(ProjectAccessService.class);
    private final MockMvc mockMvc = MockMvcBuilders
            .standaloneSetup(new TaskController(taskService, taskLogService, taskLogIncrementService, auditLogService, projectAccessService))
            .setCustomArgumentResolvers(new PrincipalArgumentResolver())
            .setControllerAdvice(new GlobalExceptionHandler())
            .build();

    @Test
    void returnsLogContentAfterTaskAccessGuard() throws Exception {
        UUID taskId = UUID.randomUUID();
        when(taskLogService.content(eq(taskId), any())).thenReturn(new TaskLogContentResponse(Map.of(
                "stdout",
                new TaskLogContentResponse.LogContent("stdout", UUID.randomUUID(), 0, 100, 1, 3, false, "ok")
        )));

        MvcResult result = mockMvc.perform(get("/api/tasks/{taskId}/log-content", taskId)
                        .param("types", "stdout")
                        .param("stdoutOffset", "2")
                        .param("stdoutLines", "1"))
                .andReturn();

        assertThat(result.getResponse().getStatus()).isEqualTo(200);
        assertThat(result.getResponse().getContentAsString()).contains("\"stdout\"").contains("\"totalLines\":3").contains("\"ok\"");
        verify(projectAccessService).requireTaskAccess(eq(taskId), any(), eq(false));
        verify(taskLogService).content(eq(taskId), any());
    }

    @Test
    void rejectsUnauthorizedBeforeReadingLogs() throws Exception {
        UUID taskId = UUID.randomUUID();
        doThrow(new ApiException(HttpStatus.NOT_FOUND, "TASK_NOT_FOUND", "任务不存在"))
                .when(projectAccessService).requireTaskAccess(eq(taskId), any(), anyBoolean());

        MvcResult result = mockMvc.perform(get("/api/tasks/{taskId}/log-content", taskId))
                .andReturn();

        assertThat(result.getResponse().getStatus()).isEqualTo(404);
        assertThat(result.getResponse().getContentAsString()).contains("TASK_NOT_FOUND");
        verify(taskLogService, never()).content(any(), any());
    }

    @Test
    void rejectsInvalidTypesAndLines() throws Exception {
        UUID taskId = UUID.randomUUID();

        MvcResult invalidType = mockMvc.perform(get("/api/tasks/{taskId}/log-content", taskId)
                        .param("types", "tool"))
                .andReturn();
        assertThat(invalidType.getResponse().getStatus()).isEqualTo(400);
        assertThat(invalidType.getResponse().getContentAsString()).contains("TASK_LOG_TYPE_INVALID");

        MvcResult negativeOffset = mockMvc.perform(get("/api/tasks/{taskId}/log-content", taskId)
                        .param("stdoutOffset", "-1"))
                .andReturn();
        assertThat(negativeOffset.getResponse().getStatus()).isEqualTo(400);
        assertThat(negativeOffset.getResponse().getContentAsString()).contains("TASK_LOG_OFFSET_INVALID");

        MvcResult tooManyLines = mockMvc.perform(get("/api/tasks/{taskId}/log-content", taskId)
                        .param("lines", "5001"))
                .andReturn();
        assertThat(tooManyLines.getResponse().getStatus()).isEqualTo(400);
        assertThat(tooManyLines.getResponse().getContentAsString()).contains("TASK_LOG_LINES_INVALID");

        verify(taskLogService, never()).content(any(), any());
    }

    @Test
    void returnsTaskLogIncrementsAfterAccessGuard() throws Exception {
        UUID taskId = UUID.randomUUID();
        TaskLogIncrementResponse response = new TaskLogIncrementResponse(
                taskId,
                8L,
                9L,
                false,
                Map.of("merged", new TaskLogIncrementResponse.LogIncrement("[STDOUT] ok\n", 1))
        );
        when(taskLogIncrementService.read(eq(taskId), any())).thenReturn(response);

        MvcResult result = mockMvc.perform(get("/api/tasks/{taskId}/log-increments", taskId)
                        .param("afterEventId", "7")
                        .param("limit", "20"))
                .andReturn();

        assertThat(result.getResponse().getStatus()).isEqualTo(200);
        assertThat(result.getResponse().getContentAsString())
                .contains("\"fromEventId\":8")
                .contains("\"latestEventId\":9")
                .contains("[STDOUT] ok");
        verify(projectAccessService).requireTaskAccess(eq(taskId), any(), eq(false));
        verify(taskLogIncrementService).read(eq(taskId), eq(new TaskLogIncrementRequest(7, 20)));
    }

    @Test
    void rejectsInvalidIncrementParametersAfterAccessGuard() throws Exception {
        UUID taskId = UUID.randomUUID();

        MvcResult invalidCursor = mockMvc.perform(get("/api/tasks/{taskId}/log-increments", taskId)
                        .param("afterEventId", "-1"))
                .andReturn();
        assertThat(invalidCursor.getResponse().getStatus()).isEqualTo(400);
        assertThat(invalidCursor.getResponse().getContentAsString()).contains("TASK_LOG_EVENT_CURSOR_INVALID");

        MvcResult invalidLimit = mockMvc.perform(get("/api/tasks/{taskId}/log-increments", taskId)
                        .param("limit", "1001"))
                .andReturn();
        assertThat(invalidLimit.getResponse().getStatus()).isEqualTo(400);
        assertThat(invalidLimit.getResponse().getContentAsString()).contains("TASK_LOG_EVENT_LIMIT_INVALID");
        verify(taskLogIncrementService, never()).read(any(), any());
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
