package cn.rvport.backend.kb;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.common.web.ApiResponse;
import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.user.UserStatus;
import cn.rvport.backend.workflow.DomainLatestFreshness;
import cn.rvport.backend.workflow.DomainLatestResponse;
import cn.rvport.backend.workflow.ProjectContextSnapshot;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.mock.web.MockHttpServletRequest;

@ExtendWith(MockitoExtension.class)
class KbScanControllerLatestTests {

    @Mock
    private KbScanService kbScanService;

    @Test
    void latestReturnsUnifiedEnvelopeAndDelegatesPrincipal() {
        UUID projectId = UUID.randomUUID();
        RvPortUserPrincipal principal = principal();
        DomainLatestResponse<KbScanResponse> latest = DomainLatestResponse.empty(new ProjectContextSnapshot(null, 7L));
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.setAttribute("traceId", "trace-test");
        when(kbScanService.latest(projectId, principal.id(), principal.superAdmin())).thenReturn(latest);

        ApiResponse<DomainLatestResponse<KbScanResponse>> response = new KbScanController(kbScanService)
                .latest(principal, projectId, request);

        assertThat(response.data().freshness()).isEqualTo(DomainLatestFreshness.EMPTY);
        assertThat(response.data().context().runtimeEnvironmentVersion()).isEqualTo(7L);
        verify(kbScanService).latest(projectId, principal.id(), principal.superAdmin());
    }

    private RvPortUserPrincipal principal() {
        return new RvPortUserPrincipal(
                UUID.randomUUID(),
                "admin",
                "Admin",
                "admin@example.test",
                true,
                false,
                UserStatus.ACTIVE
        );
    }
}
