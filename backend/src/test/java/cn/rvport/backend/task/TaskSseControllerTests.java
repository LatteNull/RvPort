package cn.rvport.backend.task;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;

import cn.rvport.backend.common.error.GlobalExceptionHandler;
import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.project.ProjectAccessService;
import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.user.UserStatus;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.core.MethodParameter;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.bind.support.WebDataBinderFactory;
import org.springframework.web.context.request.NativeWebRequest;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.method.support.ModelAndViewContainer;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

class TaskSseControllerTests {

    private final TaskEventService taskEventService = mock(TaskEventService.class);
    private final TaskSseBroker taskSseBroker = mock(TaskSseBroker.class);
    private final ProjectAccessService projectAccessService = mock(ProjectAccessService.class);
    private final MockMvc mockMvc = MockMvcBuilders
            .standaloneSetup(new TaskSseController(taskEventService, taskSseBroker, projectAccessService))
            .setCustomArgumentResolvers(new PrincipalArgumentResolver())
            .setControllerAdvice(new GlobalExceptionHandler())
            .build();

    @Test
    void replaysEventsAfterLastEventId() throws Exception {
        UUID projectId = UUID.randomUUID();
        SseEmitter emitter = new SseEmitter();
        when(taskSseBroker.subscribe(projectId)).thenReturn(emitter);
        when(taskEventService.listAfter(projectId, 42L, 500)).thenReturn(List.of());

        MvcResult result = mockMvc.perform(get("/api/projects/{projectId}/task-events", projectId)
                        .header("Last-Event-ID", "42"))
                .andReturn();

        assertThat(result.getResponse().getStatus()).isBetween(200, 299);
        verify(taskEventService).listAfter(eq(projectId), eq(42L), eq(500));
        verify(projectAccessService).requireProjectAccess(eq(projectId), org.mockito.ArgumentMatchers.any(), eq(false));
    }

    @Test
    void usesCurrentLatestEventIdAsBaselineWhenNoCursorProvided() throws Exception {
        UUID projectId = UUID.randomUUID();
        SseEmitter emitter = new SseEmitter();
        when(taskEventService.latestEventId(projectId)).thenReturn(99L);
        when(taskSseBroker.subscribe(projectId)).thenReturn(emitter);
        when(taskEventService.listAfter(projectId, 99L, 500)).thenReturn(List.of());

        MvcResult result = mockMvc.perform(get("/api/projects/{projectId}/task-events", projectId))
                .andReturn();

        assertThat(result.getResponse().getStatus()).isBetween(200, 299);
        verify(taskEventService).latestEventId(projectId);
        verify(taskEventService).listAfter(eq(projectId), eq(99L), eq(500));
    }

    @Test
    void afterEventIdOverridesLastEventId() throws Exception {
        UUID projectId = UUID.randomUUID();
        SseEmitter emitter = new SseEmitter();
        when(taskSseBroker.subscribe(projectId)).thenReturn(emitter);
        when(taskEventService.listAfter(projectId, 7L, 500)).thenReturn(List.of());

        MvcResult result = mockMvc.perform(get("/api/projects/{projectId}/task-events", projectId)
                        .queryParam("afterEventId", "7")
                        .header("Last-Event-ID", "42"))
                .andReturn();

        assertThat(result.getResponse().getStatus()).isBetween(200, 299);
        verify(taskEventService).listAfter(eq(projectId), eq(7L), eq(500));
        verify(taskEventService, never()).latestEventId(projectId);
    }

    @Test
    void rejectsInvalidLastEventId() throws Exception {
        UUID projectId = UUID.randomUUID();

        MvcResult result = mockMvc.perform(get("/api/projects/{projectId}/task-events", projectId)
                        .header("Last-Event-ID", "not-a-number"))
                .andReturn();

        assertThat(result.getResponse().getStatus()).isEqualTo(400);
        assertThat(result.getResponse().getContentAsString()).contains("SSE_LAST_EVENT_ID_INVALID");
        verify(taskSseBroker, never()).subscribe(projectId);
    }

    @Test
    void rejectsNegativeAfterEventIdBeforeSubscribing() throws Exception {
        UUID projectId = UUID.randomUUID();

        MvcResult result = mockMvc.perform(get("/api/projects/{projectId}/task-events", projectId)
                        .queryParam("afterEventId", "-1")
                        .header("Last-Event-ID", "42"))
                .andReturn();

        assertThat(result.getResponse().getStatus()).isEqualTo(400);
        assertThat(result.getResponse().getContentAsString()).contains("SSE_LAST_EVENT_ID_INVALID");
        verify(taskSseBroker, never()).subscribe(projectId);
    }

    @Test
    void rejectsUnauthorizedProjectBeforeSubscribing() throws Exception {
        UUID projectId = UUID.randomUUID();
        doThrow(new ApiException(HttpStatus.NOT_FOUND, "PROJECT_NOT_FOUND", "项目不存在"))
                .when(projectAccessService).requireProjectAccess(eq(projectId), any(), anyBoolean());

        MvcResult result = mockMvc.perform(get("/api/projects/{projectId}/task-events", projectId))
                .andReturn();

        assertThat(result.getResponse().getStatus()).isEqualTo(404);
        verify(taskSseBroker, never()).subscribe(projectId);
    }

    @Test
    void writesSseErrorWhenClientAcceptsEventStream() throws Exception {
        UUID projectId = UUID.randomUUID();
        doThrow(new ApiException(HttpStatus.NOT_FOUND, "PROJECT_NOT_FOUND", "项目不存在"))
                .when(projectAccessService).requireProjectAccess(eq(projectId), any(), anyBoolean());

        MvcResult result = mockMvc.perform(get("/api/projects/{projectId}/task-events", projectId)
                        .accept(MediaType.TEXT_EVENT_STREAM))
                .andReturn();

        assertThat(result.getResponse().getStatus()).isEqualTo(404);
        assertThat(result.getResponse().getContentType()).contains(MediaType.TEXT_EVENT_STREAM_VALUE);
        assertThat(result.getResponse().getContentAsString()).contains("event: error", "PROJECT_NOT_FOUND");
        verify(taskSseBroker, never()).subscribe(projectId);
    }

    private static final class PrincipalArgumentResolver implements HandlerMethodArgumentResolver {

        @Override
        public boolean supportsParameter(MethodParameter parameter) {
            return parameter.hasParameterAnnotation(AuthenticationPrincipal.class);
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
