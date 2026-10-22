package cn.rvport.backend.task;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.user.UserStatus;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;

class ScriptExecutionControllerTests {
    @Test
    void delegatesListAndDetail() {
        ScriptExecutionService service = mock(ScriptExecutionService.class);
        ScriptExecutionController controller = new ScriptExecutionController(service);
        RvPortUserPrincipal principal = new RvPortUserPrincipal(UUID.randomUUID(), "user", "User", "u@e.test", false, false, UserStatus.ACTIVE);
        UUID projectId = UUID.randomUUID();
        UUID executionId = UUID.randomUUID();
        MockHttpServletRequest request = new MockHttpServletRequest();
        assertThat(controller.list(principal, projectId, null, request).timestamp()).isNotNull();
        assertThat(controller.get(principal, executionId, request).timestamp()).isNotNull();
        verify(service).list(projectId, null, principal.id(), false);
        verify(service).get(executionId, principal.id(), false);
    }
}
