package cn.rvport.backend.project;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.user.UserStatus;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;

class ProjectControllerDelegationTests {

    @Test
    void delegatesEveryProjectEndpointWithPrincipalContext() {
        ProjectService service = mock(ProjectService.class);
        ProjectController controller = new ProjectController(service);
        RvPortUserPrincipal principal = new RvPortUserPrincipal(UUID.randomUUID(), "user", "User",
                "user@example.com", false, false, UserStatus.ACTIVE);
        UUID projectId = UUID.randomUUID();
        MockHttpServletRequest request = new MockHttpServletRequest();

        assertThat(controller.list(principal, null, request).timestamp()).isNotNull();
        assertThat(controller.create(principal, null, request).timestamp()).isNotNull();
        assertThat(controller.get(principal, projectId, request).timestamp()).isNotNull();
        assertThat(controller.update(principal, projectId, null, request).timestamp()).isNotNull();
        assertThat(controller.overview(principal, projectId, request).timestamp()).isNotNull();

        verify(service).list(null, principal.id(), false);
        verify(service).create(null, principal.id(), request);
        verify(service).update(projectId, null, principal.id(), false, request);
        verify(service).overview(projectId, principal.id(), false);
    }
}
