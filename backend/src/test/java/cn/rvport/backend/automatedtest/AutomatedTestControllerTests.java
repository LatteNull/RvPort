package cn.rvport.backend.automatedtest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.user.UserStatus;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;

class AutomatedTestControllerTests {
    @Test
    void delegatesAllEndpoints() {
        AutomatedTestService service = mock(AutomatedTestService.class);
        AutomatedTestController controller = new AutomatedTestController(service);
        RvPortUserPrincipal principal = new RvPortUserPrincipal(UUID.randomUUID(), "user", "User", "u@e.test", false, false, UserStatus.ACTIVE);
        UUID projectId = UUID.randomUUID();
        UUID runId = UUID.randomUUID();
        MockHttpServletRequest request = new MockHttpServletRequest();
        assertThat(controller.create(principal, projectId, null, request).timestamp()).isNotNull();
        assertThat(controller.list(principal, projectId, null, request).timestamp()).isNotNull();
        assertThat(controller.latest(principal, projectId, request).timestamp()).isNotNull();
        assertThat(controller.get(principal, runId, request).timestamp()).isNotNull();
        assertThat(controller.cancel(principal, runId, request).timestamp()).isNotNull();
        verify(service).create(projectId, null, principal.id(), false, request);
        verify(service).list(projectId, null, principal.id(), false);
        verify(service).latest(projectId, principal.id(), false);
        verify(service).get(runId, principal.id(), false);
        verify(service).cancel(runId, principal.id(), false);
    }
}
