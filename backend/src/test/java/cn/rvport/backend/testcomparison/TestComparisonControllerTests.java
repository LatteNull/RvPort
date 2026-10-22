package cn.rvport.backend.testcomparison;

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

class TestComparisonControllerTests {

    @Test
    void delegatesQueriesAndCancellation() {
        TestComparisonService service = mock(TestComparisonService.class);
        TestComparisonController controller = new TestComparisonController(service);
        RvPortUserPrincipal principal = principal();
        UUID projectId = UUID.randomUUID();
        UUID comparisonId = UUID.randomUUID();
        MockHttpServletRequest request = new MockHttpServletRequest();

        assertThat(controller.list(principal, projectId, null, request).timestamp()).isNotNull();
        assertThat(controller.get(principal, comparisonId, request).timestamp()).isNotNull();
        assertThat(controller.findings(principal, comparisonId, null, request).timestamp()).isNotNull();
        assertThat(controller.cancel(principal, comparisonId, request).timestamp()).isNotNull();

        verify(service).list(projectId, null, principal.id(), false);
        verify(service).get(comparisonId, principal.id(), false);
        verify(service).findings(comparisonId, null, principal.id(), false);
        verify(service).cancel(comparisonId, principal.id(), false);
    }

    @Test
    void downloadUsesAgentOutputMetadata() {
        TestComparisonService service = mock(TestComparisonService.class);
        TestComparisonController controller = new TestComparisonController(service);
        RvPortUserPrincipal principal = principal();
        UUID comparisonId = UUID.randomUUID();
        ByteArrayResource resource = new ByteArrayResource("output".getBytes(StandardCharsets.UTF_8));
        when(service.downloadAgentOutput(comparisonId, principal.id(), false))
                .thenReturn(new TestComparisonService.AgentOutputDownload(resource, "output.json", "application/json"));

        var response = controller.downloadAgentOutput(principal, comparisonId);

        assertThat(response.getBody()).isSameAs(resource);
        assertThat(response.getHeaders().getContentType().toString()).isEqualTo("application/json");
        assertThat(response.getHeaders().getContentDisposition().getFilename()).isEqualTo("output.json");
    }

    private RvPortUserPrincipal principal() {
        return new RvPortUserPrincipal(UUID.randomUUID(), "user", "User", "user@example.com",
                false, false, UserStatus.ACTIVE);
    }
}
