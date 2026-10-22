package cn.rvport.backend.security;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;

import cn.rvport.backend.user.UserRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.security.autoconfigure.SecurityAutoConfiguration;
import org.springframework.boot.security.autoconfigure.web.servlet.SecurityFilterAutoConfiguration;
import org.springframework.boot.security.autoconfigure.web.servlet.ServletWebSecurityAutoConfiguration;
import org.springframework.boot.test.context.runner.WebApplicationContextRunner;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.session.web.http.CookieSerializer;

class SecurityConfigurationTests {

    @Test
    void createsSecurityFilterChainAndSessionCookieWithoutRedisConnection() {
        new WebApplicationContextRunner()
                .withConfiguration(AutoConfigurations.of(
                        SecurityAutoConfiguration.class,
                        ServletWebSecurityAutoConfiguration.class,
                        SecurityFilterAutoConfiguration.class
                ))
                .withUserConfiguration(SecurityConfiguration.class)
                .withBean(UserRepository.class, () -> mock(UserRepository.class))
                .withBean(SecurityErrorWriter.class, () -> new SecurityErrorWriter(new ObjectMapper()))
                .withBean(RedisConnectionFactory.class, () -> mock(RedisConnectionFactory.class))
                .run(context -> {
                    assertThat(context).hasSingleBean(SecurityFilterChain.class);
                    assertThat(context).hasSingleBean(CookieSerializer.class);
                    assertThat(context.getStartupFailure()).isNull();
                });
    }
}
