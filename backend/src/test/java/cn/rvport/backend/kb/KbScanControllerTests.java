package cn.rvport.backend.kb;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.user.UserStatus;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.mock.web.MockHttpServletRequest;

class KbScanControllerTests {

    @Test
    void delegatesAllJsonEndpoints() {
        KbScanService service = mock(KbScanService.class);
        KbScanController controller = new KbScanController(service);
        RvPortUserPrincipal principal = principal();
        UUID projectId = UUID.randomUUID();
        UUID scanId = UUID.randomUUID();
        UUID findingId = UUID.randomUUID();
        MockHttpServletRequest request = new MockHttpServletRequest();

        assertThat(controller.create(principal, projectId, null, request).timestamp()).isNotNull();
        assertThat(controller.list(principal, projectId, null, request).timestamp()).isNotNull();
        assertThat(controller.latest(principal, projectId, request).timestamp()).isNotNull();
        assertThat(controller.get(principal, scanId, request).timestamp()).isNotNull();
        assertThat(controller.findings(principal, scanId, null, request).timestamp()).isNotNull();
        assertThat(controller.artifacts(principal, scanId, null, request).timestamp()).isNotNull();
        assertThat(controller.finding(principal, findingId, request).timestamp()).isNotNull();
        assertThat(controller.codeContext(principal, findingId, request).timestamp()).isNotNull();

        verify(service).create(projectId, null, principal.id(), false, request);
        verify(service).latest(projectId, principal.id(), false);
        verify(service).findings(scanId, null, principal.id(), false);
        verify(service).codeContext(findingId, principal.id(), false);
    }

    @Test
    void downloadEndpointsUseArtifactMetadata() {
        KbScanService service = mock(KbScanService.class);
        KbScanController controller = new KbScanController(service);
        RvPortUserPrincipal principal = principal();
        UUID scanId = UUID.randomUUID();
        UUID artifactId = UUID.randomUUID();
        ByteArrayResource resource = new ByteArrayResource("report".getBytes(StandardCharsets.UTF_8));
        var artifact = new KbScanService.DownloadableKbScanArtifact(resource, "scan.html", "text/html");
        when(service.downloadArtifact(scanId, artifactId, principal.id(), false)).thenReturn(artifact);
        when(service.downloadArtifactByFormat(scanId, "json", principal.id(), false))
                .thenReturn(new KbScanService.DownloadableKbScanArtifact(resource, "scan.json", "application/json"));

        var byId = controller.downloadArtifact(principal, scanId, artifactId);
        var byFormat = controller.downloadArtifactByFormat(principal, scanId, "json");

        assertThat(byId.getBody()).isSameAs(resource);
        assertThat(byId.getHeaders().getContentDisposition().getFilename()).isEqualTo("scan.html");
        assertThat(byFormat.getHeaders().getContentType().toString()).isEqualTo("application/json");
        assertThat(byFormat.getHeaders().getContentDisposition().getFilename()).isEqualTo("scan.json");
    }

    private RvPortUserPrincipal principal() {
        return new RvPortUserPrincipal(UUID.randomUUID(), "user", "User", "user@example.com",
                false, false, UserStatus.ACTIVE);
    }
}
