package cn.rvport.backend.mail;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.user.UserStatus;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;

class MailConfigControllerTests {
    @Test
    void delegatesGetUpdateAndConnectivityTest() {
        MailConfigService configService = mock(MailConfigService.class);
        MailDeliveryService deliveryService = mock(MailDeliveryService.class);
        MailConfigController controller = new MailConfigController(configService, deliveryService);
        RvPortUserPrincipal principal = new RvPortUserPrincipal(UUID.randomUUID(), "admin", "Admin", "a@e.test", true, false, UserStatus.ACTIVE);
        MockHttpServletRequest request = new MockHttpServletRequest();
        MailTestRequest testRequest = new MailTestRequest("to@example.com", null);
        assertThat(controller.get(request).timestamp()).isNotNull();
        assertThat(controller.update(principal, null, request).timestamp()).isNotNull();
        assertThat(controller.test(testRequest, request).timestamp()).isNotNull();
        verify(configService).currentSettings();
        verify(configService).update(null, principal.id());
        verify(deliveryService).sendTest(testRequest.to(), null);
    }
}
