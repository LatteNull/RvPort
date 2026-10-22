package cn.rvport.backend.buildvalidation;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.user.UserStatus;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;

class BuildValidationControllerTests {

    @Test
    void delegatesAllBuildEndpoints() {
        BuildValidationService service = mock(BuildValidationService.class);
        BuildValidationController controller = new BuildValidationController(service);
        RvPortUserPrincipal principal = principal();
        UUID projectId = UUID.randomUUID();
        UUID buildId = UUID.randomUUID();
        MockHttpServletRequest request = new MockHttpServletRequest();

        assertThat(controller.create(principal, projectId, null, request).timestamp()).isNotNull();
        assertThat(controller.list(principal, projectId, null, request).timestamp()).isNotNull();
        assertThat(controller.latest(principal, projectId, BuildValidationLatestMode.SOURCE_ONLY, request).timestamp()).isNotNull();
        assertThat(controller.get(principal, buildId, request).timestamp()).isNotNull();
        assertThat(controller.cancel(principal, buildId, request).timestamp()).isNotNull();

        verify(service).create(projectId, null, principal.id(), false, request);
        verify(service).latest(projectId, BuildValidationLatestMode.SOURCE_ONLY, principal.id(), false);
        verify(service).cancel(buildId, principal.id(), false);
    }

    private RvPortUserPrincipal principal() {
        return new RvPortUserPrincipal(UUID.randomUUID(), "user", "User", "user@example.com",
                false, false, UserStatus.ACTIVE);
    }
}
