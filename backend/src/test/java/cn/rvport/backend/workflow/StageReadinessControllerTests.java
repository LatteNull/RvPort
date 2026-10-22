package cn.rvport.backend.workflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.user.UserStatus;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;

class StageReadinessControllerTests {
    @Test
    void delegatesReadinessWithAuthenticatedActor() {
        StageReadinessService service = mock(StageReadinessService.class);
        StageReadinessController controller = new StageReadinessController(service);
        RvPortUserPrincipal principal = principal();
        UUID projectId = UUID.randomUUID();
        assertThat(controller.readiness(principal, projectId, StageIds.TEST, new MockHttpServletRequest()).timestamp()).isNotNull();
        verify(service).readiness(projectId, StageIds.TEST, principal.id(), false);
    }

    private static RvPortUserPrincipal principal() {
        return new RvPortUserPrincipal(UUID.randomUUID(), "user", "User", "user@example.com", false, false, UserStatus.ACTIVE);
    }
}
