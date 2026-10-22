package cn.rvport.backend.user;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import cn.rvport.backend.security.RvPortUserPrincipal;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;

class AdminUserControllerTests {

    @Test
    void delegatesEveryAdministrativeUserEndpoint() {
        AdminUserService service = mock(AdminUserService.class);
        AdminUserController controller = new AdminUserController(service);
        RvPortUserPrincipal principal = new RvPortUserPrincipal(UUID.randomUUID(), "admin", "Admin",
                "admin@example.com", true, false, UserStatus.ACTIVE);
        UUID userId = UUID.randomUUID();
        MockHttpServletRequest request = new MockHttpServletRequest();

        assertThat(controller.list(null, request).timestamp()).isNotNull();
        assertThat(controller.create(principal, null, request).timestamp()).isNotNull();
        assertThat(controller.get(userId, request).timestamp()).isNotNull();
        assertThat(controller.update(principal, userId, null, request).timestamp()).isNotNull();
        assertThat(controller.resetPassword(principal, userId, null, request).timestamp()).isNotNull();
        assertThat(controller.sendInvitation(principal, userId, request).timestamp()).isNotNull();

        verify(service).create(null, principal.id(), request);
        verify(service).update(userId, null, principal.id(), request);
        verify(service).resetPassword(userId, null, principal.id(), request);
        verify(service).sendInvitation(userId, principal.id(), request);
    }
}
