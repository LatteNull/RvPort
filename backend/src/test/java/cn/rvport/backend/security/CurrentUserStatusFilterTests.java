package cn.rvport.backend.security;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.when;
import static org.mockito.Mockito.verifyNoInteractions;

import cn.rvport.backend.user.UserRepository;
import cn.rvport.backend.user.UserStatus;
import cn.rvport.backend.user.UserView;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import jakarta.servlet.ServletException;
import java.io.IOException;
import java.time.OffsetDateTime;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.mock.web.MockFilterChain;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;

@ExtendWith(MockitoExtension.class)
class CurrentUserStatusFilterTests {

    @Mock
    private UserRepository userRepository;

    @AfterEach
    void clearSecurityContext() {
        SecurityContextHolder.clearContext();
    }

    @Test
    void rejectsDisabledUserSession() throws ServletException, IOException {
        UserView disabled = user(UserStatus.DISABLED);
        authenticate(RvPortUserPrincipal.from(disabled));
        when(userRepository.findById(disabled.id())).thenReturn(Optional.of(disabled));
        CurrentUserStatusFilter filter = new CurrentUserStatusFilter(
                userRepository,
                new SecurityErrorWriter(new ObjectMapper().registerModule(new JavaTimeModule()))
        );

        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/projects");
        request.getSession(true);
        MockHttpServletResponse response = new MockHttpServletResponse();

        filter.doFilter(request, response, new MockFilterChain());

        assertThat(response.getStatus()).isEqualTo(401);
        assertThat(response.getContentAsString()).contains("AUTH_REQUIRED");
        assertThat(SecurityContextHolder.getContext().getAuthentication()).isNull();
    }

    @Test
    void refreshesActiveUserPrincipal() throws ServletException, IOException {
        UserView active = user(UserStatus.ACTIVE);
        authenticate(RvPortUserPrincipal.from(active));
        when(userRepository.findById(active.id())).thenReturn(Optional.of(active));
        CurrentUserStatusFilter filter = new CurrentUserStatusFilter(
                userRepository,
                new SecurityErrorWriter(new ObjectMapper().registerModule(new JavaTimeModule()))
        );

        MockHttpServletResponse response = new MockHttpServletResponse();

        filter.doFilter(new MockHttpServletRequest("GET", "/api/projects"), response, new MockFilterChain());

        assertThat(response.getStatus()).isNotEqualTo(401);
        assertThat(SecurityContextHolder.getContext().getAuthentication().getPrincipal())
                .isInstanceOf(RvPortUserPrincipal.class);
    }

    @Test
    void passesThroughAnonymousAndForeignPrincipalWithoutRepositoryLookup() throws Exception {
        CurrentUserStatusFilter filter = new CurrentUserStatusFilter(
                userRepository, new SecurityErrorWriter(new ObjectMapper().registerModule(new JavaTimeModule())));
        MockFilterChain anonymousChain = new MockFilterChain();
        filter.doFilter(new MockHttpServletRequest("GET", "/api/projects"), new MockHttpServletResponse(), anonymousChain);
        assertThat(anonymousChain.getRequest()).isNotNull();

        SecurityContextHolder.getContext().setAuthentication(
                UsernamePasswordAuthenticationToken.authenticated("foreign", null, java.util.List.of()));
        MockFilterChain foreignChain = new MockFilterChain();
        filter.doFilter(new MockHttpServletRequest("GET", "/api/projects"), new MockHttpServletResponse(), foreignChain);
        assertThat(foreignChain.getRequest()).isNotNull();
        verifyNoInteractions(userRepository);
    }

    @Test
    void rejectsDeletedUserWithoutCreatingSession() throws Exception {
        UserView principalUser = user(UserStatus.ACTIVE);
        authenticate(RvPortUserPrincipal.from(principalUser));
        when(userRepository.findById(principalUser.id())).thenReturn(Optional.empty());
        CurrentUserStatusFilter filter = new CurrentUserStatusFilter(
                userRepository, new SecurityErrorWriter(new ObjectMapper().registerModule(new JavaTimeModule())));
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/projects");
        MockHttpServletResponse response = new MockHttpServletResponse();

        filter.doFilter(request, response, new MockFilterChain());

        assertThat(response.getStatus()).isEqualTo(401);
        assertThat(request.getSession(false)).isNull();
    }

    private void authenticate(RvPortUserPrincipal principal) {
        SecurityContextHolder.getContext().setAuthentication(
                UsernamePasswordAuthenticationToken.authenticated(principal, null, principal.authorities())
        );
    }

    private UserView user(UserStatus status) {
        return new UserView(
                UUID.randomUUID(),
                "developer",
                "Developer",
                null,
                false,
                false,
                status,
                null,
                OffsetDateTime.now(),
                OffsetDateTime.now()
        );
    }
}
