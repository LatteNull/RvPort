package cn.rvport.backend.dependency.autofix;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.user.UserStatus;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;

class DependencyAutoFixControllerTests {

    @Test
    void delegatesEveryEndpointWithCurrentPrincipal() {
        DependencyAutoFixService service = mock(DependencyAutoFixService.class);
        DependencyAutoFixController controller = new DependencyAutoFixController(service);
        RvPortUserPrincipal principal = principal();
        UUID projectId = UUID.randomUUID();
        UUID analysisId = UUID.randomUUID();
        UUID runId = UUID.randomUUID();
        MockHttpServletRequest request = new MockHttpServletRequest();

        assertThat(controller.candidates(principal, analysisId, null, request).timestamp()).isNotNull();
        assertThat(controller.create(principal, analysisId, null, request).timestamp()).isNotNull();
        assertThat(controller.get(principal, runId, request).timestamp()).isNotNull();
        assertThat(controller.items(principal, runId, null, request).timestamp()).isNotNull();
        assertThat(controller.list(principal, projectId, null, request).timestamp()).isNotNull();

        verify(service).candidates(analysisId, null, principal.id(), false);
        verify(service).create(analysisId, null, principal.id(), false, request);
        verify(service).get(runId, principal.id(), false);
        verify(service).items(runId, null, principal.id(), false);
        verify(service).list(projectId, null, principal.id(), false);
    }

    private RvPortUserPrincipal principal() {
        return new RvPortUserPrincipal(UUID.randomUUID(), "user", "User", "user@example.com",
                false, false, UserStatus.ACTIVE);
    }
}
