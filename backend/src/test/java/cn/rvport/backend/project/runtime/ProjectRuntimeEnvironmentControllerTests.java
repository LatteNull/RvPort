package cn.rvport.backend.project.runtime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.user.UserStatus;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;

class ProjectRuntimeEnvironmentControllerTests {
    @Test
    void delegatesGetAndUpdate() {
        ProjectRuntimeEnvironmentService service = mock(ProjectRuntimeEnvironmentService.class);
        ProjectRuntimeEnvironmentController controller = new ProjectRuntimeEnvironmentController(service);
        RvPortUserPrincipal principal = new RvPortUserPrincipal(UUID.randomUUID(), "admin", "Admin", "a@b.test", true, false, UserStatus.ACTIVE);
        UUID projectId = UUID.randomUUID();
        MockHttpServletRequest request = new MockHttpServletRequest();
        assertThat(controller.get(principal, projectId, request).timestamp()).isNotNull();
        assertThat(controller.update(principal, projectId, null, request).timestamp()).isNotNull();
        verify(service).get(projectId, principal.id(), true);
        verify(service).update(projectId, null, principal.id(), true, request);
    }
}
