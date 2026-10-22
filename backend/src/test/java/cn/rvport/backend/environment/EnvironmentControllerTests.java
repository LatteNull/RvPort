package cn.rvport.backend.environment;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.user.UserStatus;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;

class EnvironmentControllerTests {

    @Test
    void delegatesCrudAndExecutionEndpointsAndSuppliesOptionalDefaults() {
        EnvironmentService service = mock(EnvironmentService.class);
        EnvironmentController controller = new EnvironmentController(service);
        RvPortUserPrincipal principal = principal();
        UUID projectId = UUID.randomUUID();
        UUID environmentId = UUID.randomUUID();
        MockHttpServletRequest request = new MockHttpServletRequest();

        assertThat(controller.list(principal, projectId, null, request).timestamp()).isNotNull();
        assertThat(controller.create(principal, projectId, null, request).timestamp()).isNotNull();
        assertThat(controller.precheckConnection(principal, projectId, null, request).timestamp()).isNotNull();
        assertThat(controller.get(principal, environmentId, request).timestamp()).isNotNull();
        assertThat(controller.update(principal, environmentId, null, request).timestamp()).isNotNull();
        assertThat(controller.testConnectionInProject(principal, projectId, environmentId, null, request).timestamp()).isNotNull();
        assertThat(controller.check(principal, projectId, environmentId, null, request).timestamp()).isNotNull();
        assertThat(controller.collectInProject(principal, projectId, environmentId, null, request).timestamp()).isNotNull();
        assertThat(controller.runScriptInProject(principal, projectId, environmentId, null, request).timestamp()).isNotNull();
        assertThat(controller.snapshots(principal, environmentId, null, request).timestamp()).isNotNull();

        verify(service).testConnection(eq(projectId), eq(environmentId), any(EnvironmentRunRequest.class),
                eq(principal.id()), eq(false), eq(request));
        verify(service).check(eq(projectId), eq(environmentId), any(EnvironmentCheckRequest.class),
                eq(principal.id()), eq(false), eq(request));
        verify(service).collect(eq(projectId), eq(environmentId), any(EnvironmentCollectRequest.class),
                eq(principal.id()), eq(false), eq(request));
        verify(service).runScript(projectId, environmentId, null, principal.id(), false, request);
    }

    @Test
    void passesExplicitExecutionBodiesWithoutReplacingThem() {
        EnvironmentService service = mock(EnvironmentService.class);
        EnvironmentController controller = new EnvironmentController(service);
        RvPortUserPrincipal principal = principal();
        UUID projectId = UUID.randomUUID();
        UUID environmentId = UUID.randomUUID();
        MockHttpServletRequest request = new MockHttpServletRequest();
        EnvironmentRunRequest run = new EnvironmentRunRequest(30);
        EnvironmentCheckRequest check = new EnvironmentCheckRequest(null, null, 30);
        EnvironmentCollectRequest collect = new EnvironmentCollectRequest(null, 30);

        controller.testConnectionInProject(principal, projectId, environmentId, run, request);
        controller.check(principal, projectId, environmentId, check, request);
        controller.collectInProject(principal, projectId, environmentId, collect, request);

        verify(service).testConnection(projectId, environmentId, run, principal.id(), false, request);
        verify(service).check(projectId, environmentId, check, principal.id(), false, request);
        verify(service).collect(projectId, environmentId, collect, principal.id(), false, request);
    }

    private RvPortUserPrincipal principal() {
        return new RvPortUserPrincipal(UUID.randomUUID(), "user", "User", "user@example.com",
                false, false, UserStatus.ACTIVE);
    }
}
