package cn.rvport.backend.dependency;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.user.UserStatus;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;

class DependencyAnalysisControllerTests {
    @Test
    void delegatesAllAnalysisEndpoints() {
        DependencyAnalysisService service = mock(DependencyAnalysisService.class);
        DependencyAnalysisController controller = new DependencyAnalysisController(service);
        RvPortUserPrincipal principal = new RvPortUserPrincipal(UUID.randomUUID(), "user", "User", "u@e.test", false, false, UserStatus.ACTIVE);
        UUID projectId = UUID.randomUUID();
        UUID analysisId = UUID.randomUUID();
        UUID resultId = UUID.randomUUID();
        MockHttpServletRequest request = new MockHttpServletRequest();
        assertThat(controller.create(principal, projectId, null, request).timestamp()).isNotNull();
        assertThat(controller.list(principal, projectId, null, request).timestamp()).isNotNull();
        assertThat(controller.latest(principal, projectId, request).timestamp()).isNotNull();
        assertThat(controller.get(principal, analysisId, request).timestamp()).isNotNull();
        assertThat(controller.results(principal, analysisId, null, request).timestamp()).isNotNull();
        assertThat(controller.result(principal, resultId, request).timestamp()).isNotNull();
        assertThat(controller.artifacts(principal, analysisId, request).timestamp()).isNotNull();
        assertThat(controller.artifact(principal, analysisId, "JSON", request).timestamp()).isNotNull();
        verify(service).create(projectId, null, principal.id(), false, request);
        verify(service).artifact(analysisId, "JSON", principal.id(), false);
    }
}
