package cn.rvport.backend.optimization;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.mockito.Mockito.verify;
import static org.springframework.security.test.web.servlet.setup.SecurityMockMvcConfigurers.springSecurity;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;

import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.security.PasswordChangeRequiredFilter;
import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.security.SecurityErrorWriter;
import cn.rvport.backend.user.UserStatus;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpStatus;
import org.springframework.mock.web.MockServletContext;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.context.SecurityContextHolderFilter;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.support.AnnotationConfigWebApplicationContext;
import org.springframework.web.servlet.config.annotation.EnableWebMvc;

class OptimizationCycleControllerTests {

    @Test
    void unauthenticatedUserCannotAccessOptimizationApi() throws Exception {
        withMockMvc(mockMvc -> {
            MvcResult result = mockMvc.perform(get("/api/projects/" + UUID.randomUUID() + "/optimization/overview")).andReturn();

            assertThat(result.getResponse().getStatus()).isEqualTo(401);
            assertThat(result.getResponse().getContentAsString()).contains("AUTH_REQUIRED");
        });
    }

    @Test
    void authenticatedUserCanQueryOptimizationCycles() throws Exception {
        withMockMvc(mockMvc -> {
            RvPortUserPrincipal principal = principal(false);

            MvcResult result = mockMvc.perform(get("/api/projects/" + UUID.randomUUID() + "/optimization/cycles")
                            .with(SecurityMockMvcRequestPostProcessors.authentication(
                                    UsernamePasswordAuthenticationToken.authenticated(principal, null, principal.authorities())
                            )))
                    .andReturn();

            assertThat(result.getResponse().getStatus()).isEqualTo(200);
            assertThat(result.getResponse().getContentAsString()).contains("\"items\":[]");
        });
    }

    @Test
    void passwordChangeUserCannotAccessOptimizationApi() throws Exception {
        withMockMvc(mockMvc -> {
            RvPortUserPrincipal principal = principal(true);

            MvcResult result = mockMvc.perform(get("/api/projects/" + UUID.randomUUID() + "/optimization/cycles/" + UUID.randomUUID())
                            .with(SecurityMockMvcRequestPostProcessors.authentication(
                                    UsernamePasswordAuthenticationToken.authenticated(principal, null, principal.authorities())
                            )))
                    .andReturn();

            assertThat(result.getResponse().getStatus()).isEqualTo(403);
            assertThat(result.getResponse().getContentAsString()).contains("PASSWORD_CHANGE_REQUIRED");
        });
    }

    @Test
    void delegatesEveryOptimizationReadEndpoint() {
        OptimizationCycleService service = mock(OptimizationCycleService.class);
        OptimizationCycleController controller = new OptimizationCycleController(service);
        RvPortUserPrincipal principal = principal(false);
        UUID projectId = UUID.randomUUID();
        UUID cycleId = UUID.randomUUID();
        org.springframework.mock.web.MockHttpServletRequest request = new org.springframework.mock.web.MockHttpServletRequest();

        assertThat(controller.overview(principal, projectId, request).timestamp()).isNotNull();
        assertThat(controller.list(principal, projectId, null, request).timestamp()).isNotNull();
        assertThat(controller.latest(principal, projectId, request).timestamp()).isNotNull();
        assertThat(controller.get(principal, projectId, cycleId, request).timestamp()).isNotNull();

        verify(service).overview(projectId, principal.id(), false);
        verify(service).list(projectId, null, principal.id(), false);
        verify(service).latest(projectId, principal.id(), false);
        verify(service).get(projectId, cycleId, principal.id(), false);
    }

    private void withMockMvc(MockMvcAction action) throws Exception {
        SecurityContextHolder.clearContext();
        AnnotationConfigWebApplicationContext context = new AnnotationConfigWebApplicationContext();
        context.setServletContext(new MockServletContext());
        context.register(TestSecurityConfig.class);
        context.refresh();
        try {
            MockMvc mockMvc = MockMvcBuilders.webAppContextSetup(context)
                    .apply(springSecurity())
                    .build();
            action.run(mockMvc);
        } finally {
            SecurityContextHolder.clearContext();
            context.close();
        }
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

    @FunctionalInterface
    private interface MockMvcAction {
        void run(MockMvc mockMvc) throws Exception;
    }

    @Configuration
    @EnableWebSecurity
    @EnableWebMvc
    static class TestSecurityConfig {

        @Bean
        OptimizationCycleController optimizationCycleController(OptimizationCycleService optimizationCycleService) {
            return new OptimizationCycleController(optimizationCycleService);
        }

        @Bean
        OptimizationCycleService optimizationCycleService() {
            OptimizationCycleService service = mock(OptimizationCycleService.class);
            when(service.list(any(), any(), any(), anyBoolean()))
                    .thenReturn(PageResponse.of(List.of(), 1, 20, 0));
            when(service.overview(any(), any(), anyBoolean()))
                    .thenReturn(new OptimizationOverviewResponse(null, 0));
            return service;
        }

        @Bean
        SecurityFilterChain securityFilterChain(HttpSecurity http, SecurityErrorWriter securityErrorWriter) throws Exception {
            return http
                    .csrf(csrf -> csrf.disable())
                    .authorizeHttpRequests(authorize -> authorize.anyRequest().authenticated())
                    .exceptionHandling(exceptions -> exceptions
                            .authenticationEntryPoint((request, response, authException) -> securityErrorWriter.write(
                                    request,
                                    response,
                                    HttpStatus.UNAUTHORIZED,
                                    "AUTH_REQUIRED",
                                    "需要登录"
                            ))
                            .accessDeniedHandler((request, response, accessDeniedException) -> securityErrorWriter.write(
                                    request,
                                    response,
                                    HttpStatus.FORBIDDEN,
                                    "FORBIDDEN",
                                    "没有权限执行该操作"
                            )))
                    .addFilterAfter(new PasswordChangeRequiredFilter(securityErrorWriter), SecurityContextHolderFilter.class)
                    .build();
        }

        @Bean
        SecurityErrorWriter securityErrorWriter() {
            return new SecurityErrorWriter(new ObjectMapper().registerModule(new JavaTimeModule()));
        }
    }
}
