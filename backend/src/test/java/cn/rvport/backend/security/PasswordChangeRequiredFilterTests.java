package cn.rvport.backend.security;

import static org.assertj.core.api.Assertions.assertThat;

import cn.rvport.backend.user.UserStatus;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import jakarta.servlet.ServletException;
import java.io.IOException;
import java.util.UUID;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockFilterChain;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;

class PasswordChangeRequiredFilterTests {

    private final PasswordChangeRequiredFilter filter = new PasswordChangeRequiredFilter(
            new SecurityErrorWriter(new ObjectMapper().registerModule(new JavaTimeModule()))
    );

    @AfterEach
    void clearSecurityContext() {
        SecurityContextHolder.clearContext();
    }

    @Test
    void blocksBusinessApiWhenPasswordMustBeChanged() throws ServletException, IOException {
        authenticate(principal(true));
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/projects");
        MockHttpServletResponse response = new MockHttpServletResponse();

        filter.doFilter(request, response, new MockFilterChain());

        assertThat(response.getStatus()).isEqualTo(403);
        assertThat(response.getContentAsString()).contains("PASSWORD_CHANGE_REQUIRED");
    }

    @Test
    void allowsChangePasswordEndpointWhenPasswordMustBeChanged() throws ServletException, IOException {
        authenticate(principal(true));
        MockHttpServletRequest request = new MockHttpServletRequest("POST", "/api/auth/change-password");
        MockHttpServletResponse response = new MockHttpServletResponse();

        filter.doFilter(request, response, new MockFilterChain());

        assertThat(response.getStatus()).isNotEqualTo(403);
    }

    @Test
    void allowsAuthSupportEndpointsWhenPasswordMustBeChanged() throws ServletException, IOException {
        for (String path : new String[] {"/api/auth/me", "/api/auth/csrf", "/api/auth/logout"}) {
            clearSecurityContext();
            authenticate(principal(true));
            MockHttpServletRequest request = new MockHttpServletRequest("POST", path);
            MockHttpServletResponse response = new MockHttpServletResponse();

            filter.doFilter(request, response, new MockFilterChain());

            assertThat(response.getStatus()).isNotEqualTo(403);
        }
    }

    @Test
    void allowsBusinessApiWhenPasswordChangeIsNotRequired() throws ServletException, IOException {
        authenticate(principal(false));
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/projects");
        MockHttpServletResponse response = new MockHttpServletResponse();

        filter.doFilter(request, response, new MockFilterChain());

        assertThat(response.getStatus()).isNotEqualTo(403);
    }

    private void authenticate(RvPortUserPrincipal principal) {
        SecurityContextHolder.getContext().setAuthentication(
                UsernamePasswordAuthenticationToken.authenticated(principal, null, principal.authorities())
        );
    }

    private RvPortUserPrincipal principal(boolean mustChangePassword) {
        return new RvPortUserPrincipal(
                UUID.randomUUID(),
                "developer",
                "Developer",
                null,
                false,
                mustChangePassword,
                UserStatus.ACTIVE
        );
    }
}
