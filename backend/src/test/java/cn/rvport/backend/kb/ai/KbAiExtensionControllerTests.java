package cn.rvport.backend.kb.ai;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;

import cn.rvport.backend.common.error.GlobalExceptionHandler;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.task.TaskResponse;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.user.UserStatus;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.core.MethodParameter;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.MediaType;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.bind.support.WebDataBinderFactory;
import org.springframework.web.context.request.NativeWebRequest;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.method.support.ModelAndViewContainer;

class KbAiExtensionControllerTests {

    private final KbAiExtensionService service = mock(KbAiExtensionService.class);
    private final MockMvc mockMvc = MockMvcBuilders
            .standaloneSetup(new KbAiExtensionController(service))
            .setCustomArgumentResolvers(new PrincipalArgumentResolver())
            .setControllerAdvice(new GlobalExceptionHandler())
            .build();

    @Test
    void returnsEnvelopesForCreateReadinessListAndDetail() throws Exception {
        UUID projectId = UUID.randomUUID();
        UUID scanId = UUID.randomUUID();
        UUID runId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        OffsetDateTime now = OffsetDateTime.now();
        KbAiExtensionResponse run = response(runId, projectId, scanId, taskId, "SUCCEEDED", now);
        when(service.create(eq(projectId), eq(scanId), any(), any(), eq(true), any()))
                .thenReturn(new KbAiExtensionCreateResponse(
                        new TaskResponse(taskId, projectId, "KB_AI_EXTENSION", TaskStatus.PENDING, 0,
                                "pending", now, null, null, null, null, null, Map.of()),
                        run));
        when(service.readiness(eq(projectId), eq(scanId), any(), eq(true)))
                .thenReturn(new KbAiExtensionReadinessResponse(true, null, scanId, 1, true, Map.of("agentType", "CODEX")));
        when(service.list(eq(projectId), any(), any(), eq(true)))
                .thenReturn(PageResponse.of(List.of(run), 1, 20, 1));
        when(service.get(eq(runId), any(), eq(true))).thenReturn(run);

        MvcResult created = mockMvc.perform(post("/api/projects/{projectId}/kb-scans/{scanId}/ai-extensions", projectId, scanId)
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"note\":\"api test\"}")).andReturn();
        assertThat(created.getResponse().getStatus()).isBetween(200, 299);
        assertThat(created.getResponse().getContentAsString())
                .contains("\"data\"")
                .contains("\"KB_AI_EXTENSION\"");

        MvcResult readiness = mockMvc.perform(get("/api/projects/{projectId}/kb-scans/{scanId}/ai-extension-readiness", projectId, scanId))
                .andReturn();
        assertThat(readiness.getResponse().getStatus()).isBetween(200, 299);
        assertThat(readiness.getResponse().getContentAsString()).contains("\"ready\":true");

        MvcResult list = mockMvc.perform(get("/api/projects/{projectId}/kb-ai-extensions?page=1&pageSize=20&status=SUCCEEDED", projectId))
                .andReturn();
        assertThat(list.getResponse().getStatus()).isBetween(200, 299);
        assertThat(list.getResponse().getContentAsString()).contains("\"total\":1");

        MvcResult detail = mockMvc.perform(get("/api/kb-ai-extensions/{runId}", runId)).andReturn();
        assertThat(detail.getResponse().getStatus()).isBetween(200, 299);
        assertThat(detail.getResponse().getContentAsString()).contains(runId.toString());

        verify(service).create(eq(projectId), eq(scanId), any(), any(), eq(true), any());
        verify(service).readiness(eq(projectId), eq(scanId), any(), eq(true));
        verify(service).list(eq(projectId), any(), any(), eq(true));
        verify(service).get(eq(runId), any(), eq(true));
    }

    @Test
    void returnsArtifactListAndDownloadResponse() throws Exception {
        UUID runId = UUID.randomUUID();
        UUID artifactId = UUID.randomUUID();
        when(service.artifacts(eq(runId), any(), eq(true)))
                .thenReturn(List.of(new KbAiExtensionArtifactResponse(
                        artifactId,
                        UUID.randomUUID(),
                        UUID.randomUUID(),
                        "OUTPUT_RESULTS_JSONL",
                        "application/x-ndjson",
                        42L,
                        "sha",
                        Map.of(),
                        OffsetDateTime.now())));
        when(service.downloadArtifact(eq(runId), eq(artifactId), any(), eq(true)))
                .thenReturn(new KbAiExtensionService.DownloadableArtifact(
                        "kb-ai-extension-output-results.jsonl",
                        "application/x-ndjson",
                        new ByteArrayResource("{\"findingId\":\"one\"}\n".getBytes())));

        MvcResult artifacts = mockMvc.perform(get("/api/kb-ai-extensions/{runId}/artifacts", runId)).andReturn();
        assertThat(artifacts.getResponse().getStatus()).isBetween(200, 299);
        assertThat(artifacts.getResponse().getContentAsString()).contains("OUTPUT_RESULTS_JSONL");

        MvcResult download = mockMvc.perform(get("/api/kb-ai-extensions/{runId}/artifacts/{artifactId}/download", runId, artifactId))
                .andReturn();
        assertThat(download.getResponse().getStatus()).isBetween(200, 299);
        assertThat(download.getResponse().getHeader("Content-Disposition")).contains(".jsonl");
        assertThat(download.getResponse().getContentAsString()).contains("findingId");
    }

    private KbAiExtensionResponse response(UUID runId, UUID projectId, UUID scanId, UUID taskId, String status, OffsetDateTime now) {
        return new KbAiExtensionResponse(
                runId,
                projectId,
                UUID.randomUUID(),
                scanId,
                taskId,
                UUID.randomUUID(),
                UUID.randomUUID(),
                status,
                Map.of("accepted", 1),
                UUID.randomUUID(),
                UUID.randomUUID(),
                UUID.randomUUID(),
                now,
                now,
                now,
                now
        );
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
}
