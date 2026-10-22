package cn.rvport.backend.agentruntime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;

class AgentRuntimeControllerTests {
    @Test
    void delegatesListAndGet() {
        AgentRuntimeService service = mock(AgentRuntimeService.class);
        AgentRuntimeController controller = new AgentRuntimeController(service);
        UUID id = UUID.randomUUID();
        assertThat(controller.list(new MockHttpServletRequest()).timestamp()).isNotNull();
        assertThat(controller.get(id, new MockHttpServletRequest()).timestamp()).isNotNull();
        verify(service).list();
        verify(service).get(id);
    }
}
