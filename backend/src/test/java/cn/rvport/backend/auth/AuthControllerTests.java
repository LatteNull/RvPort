package cn.rvport.backend.auth;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;

import cn.rvport.backend.audit.AuditLogService;
import cn.rvport.backend.common.error.GlobalExceptionHandler;
import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.user.UserResponse;
import cn.rvport.backend.user.UserStatus;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import java.time.OffsetDateTime;
import java.util.UUID;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

class AuthControllerTests {

    private final AuthService authService = org.mockito.Mockito.mock(AuthService.class);
    private final AuditLogService auditLogService = mock(AuditLogService.class);
    private final MockMvc mockMvc = MockMvcBuilders
            .standaloneSetup(new AuthController(authService, auditLogService))
            .setControllerAdvice(new GlobalExceptionHandler())
            .build();

    @AfterEach
    void clearSecurityContext() {
        SecurityContextHolder.clearContext();
    }

    @Test
    void loginReturnsEnvelopeWithoutPasswordFields() throws Exception {
        when(authService.login(any(), any())).thenReturn(new LoginResponse(new UserResponse(
                UUID.randomUUID(),
                "admin",
                "Admin",
                null,
                true,
                true,
                UserStatus.ACTIVE,
                null,
                OffsetDateTime.now(),
                OffsetDateTime.now()
        )));

        String body = new ObjectMapper()
                .registerModule(new JavaTimeModule())
                .writeValueAsString(new LoginRequest("admin", "Admin123"));

        MvcResult result = mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andReturn();

        assertThat(result.getResponse().getStatus()).isBetween(200, 299);
        assertThat(result.getResponse().getContentAsString())
                .contains("\"username\":\"admin\"")
                .contains("\"isSuperAdmin\":true")
                .doesNotContain("password")
                .doesNotContain("roles")
                .doesNotContain("permissions");
    }

    @Test
    void logoutInvalidatesSessionAndReturnsEnvelope() throws Exception {
        var principal = new RvPortUserPrincipal(
                UUID.randomUUID(),
                "admin",
                "Admin",
                null,
                true,
                false,
                UserStatus.ACTIVE
        );
        SecurityContextHolder.getContext().setAuthentication(
                UsernamePasswordAuthenticationToken.authenticated(principal, null, principal.authorities())
        );
        MockHttpSession session = new MockHttpSession();

        MvcResult result = mockMvc.perform(post("/api/auth/logout")
                        .session(session))
                .andReturn();

        assertThat(result.getResponse().getStatus()).isBetween(200, 299);
        assertThat(result.getResponse().getContentAsString()).contains("\"loggedOut\":true");
        assertThat(session.isInvalid()).isTrue();
        assertThat(result.getResponse().getCookie("RVPORT_SESSION").getMaxAge()).isZero();
        verify(auditLogService).record(any(), org.mockito.Mockito.eq("auth.logout"), org.mockito.Mockito.eq("user"), any(), any(), any());
    }
}
