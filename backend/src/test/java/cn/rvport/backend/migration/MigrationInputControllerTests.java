package cn.rvport.backend.migration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.user.UserStatus;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;

class MigrationInputControllerTests {
    @Test
    void delegatesAllMigrationInputEndpoints() {
        MigrationInputService service = mock(MigrationInputService.class);
        MigrationInputController controller = new MigrationInputController(service);
        RvPortUserPrincipal principal = new RvPortUserPrincipal(UUID.randomUUID(), "user", "User", "u@e.test", false, false, UserStatus.ACTIVE);
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        UUID inputId = UUID.randomUUID();
        MockHttpServletRequest request = new MockHttpServletRequest();
        assertThat(controller.list(principal, projectId, revisionId, null, request).timestamp()).isNotNull();
        assertThat(controller.importRefs(principal, projectId, revisionId, null, request).timestamp()).isNotNull();
        assertThat(controller.autoMerge(principal, projectId, revisionId, null, request).timestamp()).isNotNull();
        assertThat(controller.detail(principal, inputId, request).timestamp()).isNotNull();
        assertThat(controller.update(principal, inputId, null, request).timestamp()).isNotNull();
        verify(service).list(projectId, revisionId, null, principal.id(), false);
        verify(service).detail(inputId, principal.id(), false);
    }
}
