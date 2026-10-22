package cn.rvport.backend.analysis;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.artifact.StoredArtifactOwnerType;
import cn.rvport.backend.artifact.StoredArtifactResource;
import cn.rvport.backend.artifact.StoredArtifactView;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.user.UserStatus;
import jakarta.servlet.http.HttpServletRequest;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.core.io.ByteArrayResource;

@ExtendWith(MockitoExtension.class)
class SpecializedAnalysisControllerTests {

    @Mock SpecializedAnalysisService service;
    @Mock HttpServletRequest request;

    @Test
    void delegatesEveryDomainEndpointAndBuildsDownloadResponses() {
        SpecializedAnalysisController controller = new SpecializedAnalysisController(service);
        UUID projectId = UUID.randomUUID();
        UUID runId = UUID.randomUUID();
        UUID findingId = UUID.randomUUID();
        RvPortUserPrincipal principal = new RvPortUserPrincipal(UUID.randomUUID(), "admin", "Admin",
                "admin@example.com", true, false, UserStatus.ACTIVE);
        SpecializedAnalysisListRequest runs = new SpecializedAnalysisListRequest(1, 20, null, null, null, null);
        SpecializedFindingListRequest findings = new SpecializedFindingListRequest(1, 20, null, null, null, null,
                null, null, null, null);
        when(service.list(eq(projectId), any(), eq(runs), eq(principal.id()), eq(true)))
                .thenReturn(PageResponse.of(List.of(), 1, 20, 0));
        when(service.findings(eq(projectId), any(), eq(runId), eq(findings), eq(principal.id()), eq(true)))
                .thenReturn(PageResponse.of(List.of(), 1, 20, 0));
        StoredArtifactResource artifact = artifact(projectId, runId);
        when(service.download(eq(projectId), any(), eq(runId), any(), eq(principal.id()), eq(true)))
                .thenReturn(artifact);

        controller.createFloating(principal, projectId, request);
        controller.createMemory(principal, projectId, request);
        controller.listFloating(principal, projectId, runs, request);
        controller.listMemory(principal, projectId, runs, request);
        controller.latestFloating(principal, projectId, request);
        controller.latestMemory(principal, projectId, request);
        controller.floating(principal, projectId, runId, request);
        controller.memory(principal, projectId, runId, request);
        controller.floatingFindings(principal, projectId, runId, findings, request);
        controller.memoryFindings(principal, projectId, runId, findings, request);
        controller.floatingFinding(principal, projectId, findingId, request);
        controller.memoryFinding(principal, projectId, findingId, request);
        var json = controller.floatingArtifact(principal, projectId, runId, "json");
        var audit = controller.memoryArtifact(principal, projectId, runId, "audit");

        verify(service).create(projectId, SpecializedAnalyzerType.FLOATING_POINT, principal.id(), true);
        verify(service).create(projectId, SpecializedAnalyzerType.MEMORY_ORDER, principal.id(), true);
        verify(service).finding(projectId, SpecializedAnalyzerType.FLOATING_POINT, findingId, principal.id(), true);
        verify(service).finding(projectId, SpecializedAnalyzerType.MEMORY_ORDER, findingId, principal.id(), true);
        assertThat(json.getHeaders().getContentDisposition().getFilename()).endsWith(".json");
        assertThat(audit.getHeaders().getContentDisposition().getFilename()).endsWith(".tgz");
        assertThat(json.getBody()).isSameAs(artifact.resource());
    }

    private StoredArtifactResource artifact(UUID projectId, UUID runId) {
        StoredArtifactView view = new StoredArtifactView(UUID.randomUUID(), projectId, null,
                StoredArtifactOwnerType.SPECIALIZED_ANALYSIS, runId, "RESULT", "bucket", "result",
                "application/json", 2, "a".repeat(64), Map.of(), OffsetDateTime.now());
        return new StoredArtifactResource(view, new ByteArrayResource("{}".getBytes()));
    }
}
