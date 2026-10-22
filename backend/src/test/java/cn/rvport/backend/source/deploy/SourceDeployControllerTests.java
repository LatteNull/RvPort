package cn.rvport.backend.source.deploy;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.user.UserStatus;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.mock.web.MockHttpServletRequest;

class SourceDeployControllerTests {

    @Test
    void rejectsDeprecatedCreateAndDelegatesReadOperations() {
        SourceDeployService service = mock(SourceDeployService.class);
        SourceDeployController controller = new SourceDeployController(service);
        RvPortUserPrincipal principal = principal();
        UUID projectId = UUID.randomUUID();
        UUID deploymentId = UUID.randomUUID();
        MockHttpServletRequest request = new MockHttpServletRequest();

        assertThatThrownBy(() -> controller.create(principal, projectId, null, request))
                .isInstanceOfSatisfying(ApiException.class, failure -> {
                    assertThat(failure.status()).isEqualTo(HttpStatus.GONE);
                    assertThat(failure.code()).isEqualTo("SOURCE_DEPLOYMENT_CREATE_DEPRECATED");
                });
        assertThat(controller.list(principal, projectId, null, request).timestamp()).isNotNull();
        assertThat(controller.get(principal, deploymentId, request).timestamp()).isNotNull();
        assertThat(controller.cancel(principal, deploymentId, request).timestamp()).isNotNull();

        verify(service).list(projectId, null, principal.id(), false);
        verify(service).get(deploymentId, principal.id(), false);
        verify(service).cancel(deploymentId, principal.id(), false);
    }

    private RvPortUserPrincipal principal() {
        return new RvPortUserPrincipal(UUID.randomUUID(), "user", "User", "user@example.com",
                false, false, UserStatus.ACTIVE);
    }
}
