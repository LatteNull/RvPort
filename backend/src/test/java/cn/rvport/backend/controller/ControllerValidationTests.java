package cn.rvport.backend.controller;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;

import cn.rvport.backend.audit.AuditLogService;
import cn.rvport.backend.auth.AuthController;
import cn.rvport.backend.auth.AuthService;
import cn.rvport.backend.buildvalidation.BuildValidationController;
import cn.rvport.backend.buildvalidation.BuildValidationService;
import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.common.error.GlobalExceptionHandler;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.environment.EnvironmentController;
import cn.rvport.backend.environment.EnvironmentService;
import cn.rvport.backend.project.ProjectAccessService;
import cn.rvport.backend.project.ProjectController;
import cn.rvport.backend.project.ProjectService;
import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.source.SourceController;
import cn.rvport.backend.source.SourceCompareService;
import cn.rvport.backend.source.SourceService;
import cn.rvport.backend.task.TaskController;
import cn.rvport.backend.task.TaskLogService;
import cn.rvport.backend.task.TaskLogIncrementService;
import cn.rvport.backend.task.TaskService;
import cn.rvport.backend.user.AdminUserController;
import cn.rvport.backend.user.AdminUserService;
import cn.rvport.backend.user.UserStatus;
import cn.rvport.backend.worker.AdminWorkerController;
import cn.rvport.backend.worker.WorkerManagementService;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.core.MethodParameter;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.bind.support.WebDataBinderFactory;
import org.springframework.web.context.request.NativeWebRequest;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.method.support.ModelAndViewContainer;
import org.springframework.web.multipart.MaxUploadSizeExceededException;

class ControllerValidationTests {

    @Test
    void authControllerReturnsValidationEnvelopeForUsernameAndPasswordLimits() throws Exception {
        MockMvc mockMvc = mockMvc(new AuthController(mock(AuthService.class), mock(AuditLogService.class)));

        assertValidation(postJson(mockMvc, "/api/auth/login", "{\"username\":\"" + "u".repeat(65) + "\",\"password\":\"Admin123\"}"));
        assertValidation(postJson(mockMvc, "/api/auth/login", "{\"username\":\"admin\",\"password\":\"" + "P".repeat(17) + "\"}"));
        assertValidation(postJson(mockMvc, "/api/auth/change-password", "{\"currentPassword\":\"OldPass123\",\"newPassword\":\"" + "P".repeat(17) + "\"}"));
        assertValidation(postJson(mockMvc, "/api/auth/invitations/accept", "{\"token\":\"token\",\"newPassword\":\"" + "P".repeat(17) + "\"}"));
        assertValidation(postJson(mockMvc, "/api/auth/password-resets/confirm", "{\"token\":\"token\",\"newPassword\":\"" + "P".repeat(17) + "\"}"));
    }

    @Test
    void adminUserControllerReturnsValidationEnvelopeForInvalidCreateUpdateAndReset() throws Exception {
        MockMvc mockMvc = mockMvc(new AdminUserController(mock(AdminUserService.class)));

        assertValidation(postJson(mockMvc, "/api/admin/users", "{}"));
        assertValidation(postJson(mockMvc, "/api/admin/users", "{\"username\":\"" + "u".repeat(65) + "\",\"email\":\"dev@example.com\"}"));
        assertValidation(patchJson(mockMvc, "/api/admin/users/{id}", UUID.randomUUID(), "{\"email\":\"bad-email\"}"));
        assertValidation(postJson(mockMvc, "/api/admin/users/{id}/reset-password", UUID.randomUUID(), "{}"));
        assertValidation(postJson(mockMvc, "/api/admin/users/{id}/reset-password", UUID.randomUUID(), "{\"newPassword\":\"" + "P".repeat(17) + "\"}"));
    }

    @Test
    void adminWorkerControllerReturnsValidationEnvelopeForInvalidPagingAndConcurrency() throws Exception {
        MockMvc mockMvc = mockMvc(new AdminWorkerController(mock(WorkerManagementService.class)));

        assertValidation(mockMvc.perform(get("/api/admin/workers?page=0&pageSize=20")).andReturn());
        assertValidation(mockMvc.perform(get("/api/admin/workers?page=1&pageSize=201")).andReturn());
        assertValidation(mockMvc.perform(put("/api/admin/workers/{workerInstanceId}/concurrency", "worker-1")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"concurrencyLimit\":-1}")).andReturn());
    }

    @Test
    void projectControllerReturnsValidationEnvelopeAndSuccessEnvelope() throws Exception {
        ProjectService projectService = mock(ProjectService.class);
        when(projectService.list(any(), any(), anyBoolean())).thenReturn(PageResponse.of(List.of(), 1, 20, 0));
        MockMvc mockMvc = mockMvc(new ProjectController(projectService));

        assertValidation(postJson(mockMvc, "/api/projects", "{}"));
        assertValidation(patchJson(mockMvc, "/api/projects/{id}", UUID.randomUUID(), "{\"name\":\"" + "x".repeat(161) + "\"}"));

        MvcResult list = mockMvc.perform(get("/api/projects?page=1&pageSize=20")).andReturn();
        assertThat(list.getResponse().getStatus()).isBetween(200, 299);
        assertThat(list.getResponse().getContentAsString())
                .contains("\"data\"")
                .contains("\"items\":[]")
                .contains("\"traceId\"");

        assertValidation(mockMvc.perform(get("/api/projects?page=0&pageSize=20")).andReturn());
    }

    @Test
    void sourceControllerReturnsErrorEnvelopeForMultipartAndGitValidation() throws Exception {
        SourceService sourceService = mock(SourceService.class);
        when(sourceService.uploadArchive(any(), any(), any(), any(), anyBoolean(), any(), anyBoolean(), any()))
                .thenThrow(new ApiException(HttpStatus.BAD_REQUEST, "SOURCE_ARCHIVE_INVALID", "源码包不能为空"));
        MockMvc mockMvc = mockMvc(new SourceController(sourceService, mock(SourceCompareService.class)));
        UUID projectId = UUID.randomUUID();

        MvcResult upload = mockMvc.perform(multipart("/api/projects/{projectId}/sources/archive", projectId)
                        .file(new MockMultipartFile("file", "empty.zip", "application/zip", new byte[0])))
                .andReturn();
        assertThat(upload.getResponse().getStatus()).isEqualTo(400);
        assertThat(upload.getResponse().getContentAsString()).contains("SOURCE_ARCHIVE_INVALID");

        assertValidation(postJson(mockMvc, "/api/projects/{projectId}/sources/git-sync", projectId, "{}"));
    }

    @Test
    void sourceControllerReturnsSafeEnvelopeForUploadSizeLimit() throws Exception {
        SourceService sourceService = mock(SourceService.class);
        when(sourceService.uploadArchive(any(), any(), any(), any(), anyBoolean(), any(), anyBoolean(), any()))
                .thenThrow(new MaxUploadSizeExceededException(1));
        MockMvc mockMvc = mockMvc(new SourceController(sourceService, mock(SourceCompareService.class)));
        UUID projectId = UUID.randomUUID();

        MvcResult upload = mockMvc.perform(multipart("/api/projects/{projectId}/sources/archive", projectId)
                        .file(new MockMultipartFile("file", "large.zip", "application/zip", "demo".getBytes())))
                .andReturn();

        assertThat(upload.getResponse().getStatus()).isEqualTo(413);
        assertThat(upload.getResponse().getContentAsString())
                .contains("UPLOAD_SIZE_LIMIT_EXCEEDED")
                .contains("traceId")
                .contains("timestamp")
                .doesNotContain("FileSizeLimitExceededException")
                .doesNotContain("MaxUploadSizeExceededException");
    }

    @Test
    void environmentControllerReturnsValidationEnvelopeForCreateUpdateRunScriptAndPaging() throws Exception {
        MockMvc mockMvc = mockMvc(new EnvironmentController(mock(EnvironmentService.class)));
        UUID projectId = UUID.randomUUID();
        UUID environmentId = UUID.randomUUID();

        assertValidation(postJson(mockMvc, "/api/projects/{projectId}/environments", projectId, "{}"));
        assertValidation(patchJson(mockMvc, "/api/environments/{environmentId}", environmentId, "{\"sshPort\":0}"));
        assertValidation(postJson(mockMvc, "/api/projects/{projectId}/environments/{environmentId}/scripts", projectId, environmentId, "{}"));
        assertValidation(mockMvc.perform(get("/api/projects/{projectId}/environments?page=0&pageSize=20", projectId)).andReturn());
        assertValidation(mockMvc.perform(get("/api/environments/{environmentId}/snapshots?page=1&pageSize=201", environmentId)).andReturn());
    }

    @Test
    void buildValidationControllerReturnsValidationEnvelopeForCreateAndPaging() throws Exception {
        MockMvc mockMvc = mockMvc(new BuildValidationController(mock(BuildValidationService.class)));
        UUID projectId = UUID.randomUUID();

        assertValidation(postJson(mockMvc, "/api/projects/{projectId}/builds", projectId, "{}"));
        assertValidation(postJson(mockMvc, "/api/projects/{projectId}/builds", projectId,
                "{\"sourceDeploymentIds\":[\"" + UUID.randomUUID() + "\"],\"script\":\"\",\"timeoutSeconds\":60}"));
        assertValidation(postJson(mockMvc, "/api/projects/{projectId}/builds", projectId,
                "{\"sourceDeploymentIds\":[\"" + UUID.randomUUID() + "\"],\"script\":\"make\",\"timeoutSeconds\":9}"));
        assertValidation(mockMvc.perform(get("/api/projects/{projectId}/builds?page=0&pageSize=20", projectId)).andReturn());
        assertValidation(mockMvc.perform(get("/api/projects/{projectId}/builds?page=1&pageSize=201", projectId)).andReturn());
    }

    @Test
    void taskControllerReturnsErrorEnvelopeForTaskAndLogBoundaries() throws Exception {
        TaskService taskService = mock(TaskService.class);
        TaskLogService taskLogService = mock(TaskLogService.class);
        ProjectAccessService projectAccessService = mock(ProjectAccessService.class);
        when(taskService.get(any(), any(), anyBoolean())).thenThrow(new ApiException(HttpStatus.NOT_FOUND, "TASK_NOT_FOUND", "任务不存在"));
        when(taskService.cancel(any(), any(), anyBoolean())).thenThrow(new ApiException(HttpStatus.NOT_FOUND, "TASK_NOT_FOUND", "任务不存在"));
        doThrow(new ApiException(HttpStatus.NOT_FOUND, "TASK_LOG_NOT_FOUND", "任务日志不存在"))
                .when(projectAccessService).requireTaskLogAccess(any(), any(), any(), anyBoolean());
        MockMvc mockMvc = mockMvc(new TaskController(taskService, taskLogService, mock(TaskLogIncrementService.class), mock(AuditLogService.class), projectAccessService));
        UUID taskId = UUID.randomUUID();

        MvcResult getTask = mockMvc.perform(get("/api/tasks/{taskId}", taskId)).andReturn();
        assertThat(getTask.getResponse().getStatus()).isEqualTo(404);
        assertThat(getTask.getResponse().getContentAsString()).contains("TASK_NOT_FOUND");

        MvcResult cancel = mockMvc.perform(post("/api/tasks/{taskId}/cancel", taskId)).andReturn();
        assertThat(cancel.getResponse().getStatus()).isEqualTo(404);
        assertThat(cancel.getResponse().getContentAsString()).contains("TASK_NOT_FOUND");

        MvcResult logs = mockMvc.perform(get("/api/tasks/{taskId}/logs?page=1&pageSize=20", taskId)).andReturn();
        assertThat(logs.getResponse().getStatus()).isBetween(200, 299);
        assertThat(logs.getResponse().getContentAsString()).contains("\"data\"");

        MvcResult download = mockMvc.perform(get("/api/tasks/{taskId}/logs/{logId}/download", taskId, UUID.randomUUID())).andReturn();
        assertThat(download.getResponse().getStatus()).isEqualTo(404);
        assertThat(download.getResponse().getContentAsString()).contains("TASK_LOG_NOT_FOUND");
    }

    private MockMvc mockMvc(Object controller) {
        return MockMvcBuilders.standaloneSetup(controller)
                .setCustomArgumentResolvers(new PrincipalArgumentResolver())
                .setControllerAdvice(new GlobalExceptionHandler())
                .build();
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
                    "admin",
                    "Admin",
                    null,
                    true,
                    false,
                    UserStatus.ACTIVE
            );
        }
    }

    private MvcResult postJson(MockMvc mockMvc, String path, Object... vars) throws Exception {
        String body = vars.length > 0 && vars[vars.length - 1] instanceof String
                ? (String) vars[vars.length - 1]
                : "{}";
        Object[] pathVars = vars.length > 0 && vars[vars.length - 1] instanceof String
                ? java.util.Arrays.copyOf(vars, vars.length - 1)
                : vars;
        return mockMvc.perform(post(path, pathVars).contentType(MediaType.APPLICATION_JSON).content(body)).andReturn();
    }

    private MvcResult patchJson(MockMvc mockMvc, String path, Object... vars) throws Exception {
        String body = vars.length > 0 && vars[vars.length - 1] instanceof String
                ? (String) vars[vars.length - 1]
                : "{}";
        Object[] pathVars = vars.length > 0 && vars[vars.length - 1] instanceof String
                ? java.util.Arrays.copyOf(vars, vars.length - 1)
                : vars;
        return mockMvc.perform(patch(path, pathVars).contentType(MediaType.APPLICATION_JSON).content(body)).andReturn();
    }

    private void assertValidation(MvcResult result) throws Exception {
        assertThat(result.getResponse().getStatus()).isEqualTo(400);
        assertThat(result.getResponse().getContentAsString())
                .contains("VALIDATION_ERROR")
                .contains("traceId")
                .contains("timestamp");
    }
}
