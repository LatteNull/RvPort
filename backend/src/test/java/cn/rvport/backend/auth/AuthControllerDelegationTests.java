package cn.rvport.backend.auth;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import cn.rvport.backend.audit.AuditLogService;
import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.user.UserStatus;
import java.util.UUID;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.csrf.CsrfToken;

class AuthControllerDelegationTests {

    private final AuthService service = mock(AuthService.class);
    private final AuditLogService auditService = mock(AuditLogService.class);
    private final AuthController controller = new AuthController(service, auditService);
    private final MockHttpServletRequest request = new MockHttpServletRequest();

    @AfterEach
    void clearSecurityContext() {
        SecurityContextHolder.clearContext();
    }

    @Test
    void delegatesAllAuthenticationActionsAndBuildsCsrfResponse() {
        RvPortUserPrincipal principal = principal();
        CsrfToken token = mock(CsrfToken.class);
        org.mockito.Mockito.when(token.getHeaderName()).thenReturn("X-CSRF-TOKEN");
        org.mockito.Mockito.when(token.getParameterName()).thenReturn("_csrf");
        org.mockito.Mockito.when(token.getToken()).thenReturn("token");

        assertThat(controller.csrf(token, request).data().token()).isEqualTo("token");
        assertThat(controller.login(null, request).timestamp()).isNotNull();
        assertThat(controller.me(principal, request).timestamp()).isNotNull();
        assertThat(controller.changePassword(principal, null, request).timestamp()).isNotNull();
        assertThat(controller.updateProfile(principal, null, request).timestamp()).isNotNull();
        assertThat(controller.acceptInvitation(null, request).timestamp()).isNotNull();
        assertThat(controller.requestPasswordReset(null, request).data()).containsEntry("accepted", true);
        assertThat(controller.confirmPasswordReset(null, request).timestamp()).isNotNull();

        verify(service).changePassword(principal, null, request);
        verify(service).requestPasswordReset(null, request);
    }

    @Test
    void logoutAuditsAuthenticatedPrincipalInvalidatesSessionAndExpiresCookie() {
        RvPortUserPrincipal principal = principal();
        SecurityContextHolder.getContext().setAuthentication(
                UsernamePasswordAuthenticationToken.authenticated(principal, null, principal.authorities()));
        request.getSession(true);
        MockHttpServletResponse response = new MockHttpServletResponse();

        assertThat(controller.logout(request, response).data()).containsEntry("loggedOut", true);

        assertThat(request.getSession(false)).isNull();
        assertThat(response.getCookie("RVPORT_SESSION")).satisfies(cookie -> {
            assertThat(cookie.getMaxAge()).isZero();
            assertThat(cookie.isHttpOnly()).isTrue();
            assertThat(cookie.getPath()).isEqualTo("/");
        });
        assertThat(SecurityContextHolder.getContext().getAuthentication()).isNull();
        verify(auditService).record(principal.id(), "auth.logout", "user", principal.id(),
                java.util.Map.of("username", principal.username()), request);
    }

    @Test
    void anonymousLogoutStillExpiresCookieWithoutAuditOrSession() {
        MockHttpServletResponse response = new MockHttpServletResponse();

        assertThat(controller.logout(request, response).data()).containsEntry("loggedOut", true);

        assertThat(response.getCookie("RVPORT_SESSION").getMaxAge()).isZero();
        org.mockito.Mockito.verifyNoInteractions(auditService);
    }

    private RvPortUserPrincipal principal() {
        return new RvPortUserPrincipal(UUID.randomUUID(), "user", "User", "user@example.com",
                false, false, UserStatus.ACTIVE);
    }
}
