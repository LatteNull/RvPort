package cn.rvport.backend.security;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.session.web.http.DefaultCookieSerializer;

class SecurityCoreConfigurationTests {

    @Test
    void suppliesPasswordEncoderAndRejectingFallbackUserDetailsService() {
        SecurityCoreConfiguration configuration = new SecurityCoreConfiguration();
        String encoded = configuration.passwordEncoder().encode("Password1");

        assertThat(encoded).isNotEqualTo("Password1");
        assertThat(configuration.passwordEncoder().matches("Password1", encoded)).isTrue();
        assertThatThrownBy(() -> configuration.userDetailsService().loadUserByUsername("missing"))
                .isInstanceOf(UsernameNotFoundException.class)
                .hasMessage("missing");
    }

    @Test
    void configuresStableSessionCookieContract() {
        SecurityConfiguration configuration = new SecurityConfiguration();
        assertThat(configuration.cookieSerializer()).isInstanceOf(DefaultCookieSerializer.class);
    }
}
