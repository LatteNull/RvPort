package cn.rvport.backend.user;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.springframework.security.test.web.servlet.setup.SecurityMockMvcConfigurers.springSecurity;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;

import cn.rvport.backend.security.RvPortUserPrincipal;
import cn.rvport.backend.security.SecurityErrorWriter;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpStatus;
import org.springframework.mock.web.MockServletContext;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.support.AnnotationConfigWebApplicationContext;

class AdminUserControllerSecurityTests {

    @ParameterizedTest
    @ValueSource(strings = {"/api/admin/users", "/api/admin/configs/mail",
            "/api/admin/model-profiles", "/api/admin/model-stage-assignments"})
    void normalUserCannotAccessAdminEndpoints(String path) throws Exception {
        AnnotationConfigWebApplicationContext context = new AnnotationConfigWebApplicationContext();
        context.setServletContext(new MockServletContext());
        context.register(TestSecurityConfig.class);
        context.refresh();
        try {
            MockMvc mockMvc = MockMvcBuilders.webAppContextSetup(context)
                    .apply(springSecurity())
                    .build();
            RvPortUserPrincipal principal = new RvPortUserPrincipal(
                    UUID.randomUUID(),
                    "developer",
                    "Developer",
                    null,
                    false,
                    false,
                    UserStatus.ACTIVE
            );

            MvcResult result = mockMvc.perform(get(path)
                            .with(SecurityMockMvcRequestPostProcessors.authentication(
                                    UsernamePasswordAuthenticationToken.authenticated(
                                            principal,
                                            null,
                                            principal.authorities()
                                    )
                            )))
                    .andReturn();

            assertThat(result.getResponse().getStatus()).isEqualTo(403);
            assertThat(result.getResponse().getContentAsString())
                    .contains("FORBIDDEN")
                    .doesNotContain("PASSWORD_CHANGE_REQUIRED");
        } finally {
            context.close();
        }
    }

    @Configuration
    @EnableWebSecurity
    static class TestSecurityConfig {

        @Bean
        AdminUserController adminUserController() {
            return new AdminUserController(mock(AdminUserService.class));
        }

        @Bean
        SecurityFilterChain securityFilterChain(HttpSecurity http, SecurityErrorWriter securityErrorWriter) throws Exception {
            return http
                    .csrf(csrf -> csrf.disable())
                    .authorizeHttpRequests(authorize -> authorize
                            .requestMatchers("/api/admin/users", "/api/admin/users/**", "/api/admin/configs", "/api/admin/configs/**",
                                    "/api/admin/model-profiles", "/api/admin/model-profiles/**",
                                    "/api/admin/model-stage-assignments").hasAuthority("SUPER_ADMIN")
                            .anyRequest().authenticated())
                    .exceptionHandling(exceptions -> exceptions
                            .accessDeniedHandler((request, response, accessDeniedException) -> securityErrorWriter.write(
                                    request,
                                    response,
                                    HttpStatus.FORBIDDEN,
                                    "FORBIDDEN",
                                    "没有权限执行该操作"
                            )))
                    .build();
        }

        @Bean
        SecurityErrorWriter securityErrorWriter() {
            return new SecurityErrorWriter(new ObjectMapper().registerModule(new JavaTimeModule()));
        }
    }
}
