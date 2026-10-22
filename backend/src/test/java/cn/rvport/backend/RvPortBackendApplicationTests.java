package cn.rvport.backend;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import cn.rvport.backend.config.RvPortAppMode;
import org.junit.jupiter.api.Test;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.WebApplicationType;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

class RvPortBackendApplicationTests {

    @Test
    void declaresApplicationAndSchedulingConfiguration() {
        assertThat(RvPortBackendApplication.class).hasAnnotation(SpringBootApplication.class);
        assertThat(RvPortBackendApplication.class).hasAnnotation(EnableScheduling.class);
    }

    @Test
    void appModeDefaultsAndNormalizesInput() {
        assertThat(RvPortAppMode.from(null)).isEqualTo(RvPortAppMode.COMBINED);
        assertThat(RvPortAppMode.from("  ")).isEqualTo(RvPortAppMode.COMBINED);
        assertThat(RvPortAppMode.from("worker")).isEqualTo(RvPortAppMode.WORKER);
        assertThat(RvPortAppMode.from("api")).isEqualTo(RvPortAppMode.API);
    }

    @Test
    void createsNonWebApplicationOnlyForWorkerMode() {
        assertThat(RvPortBackendApplication.createApplication("worker").getWebApplicationType())
                .isEqualTo(WebApplicationType.NONE);
        assertThat(RvPortBackendApplication.createApplication("combined").getWebApplicationType())
                .isNotEqualTo(WebApplicationType.NONE);
        assertThat(RvPortBackendApplication.createApplication("api").getWebApplicationType())
                .isNotEqualTo(WebApplicationType.NONE);
    }

    @Test
    void mainDelegatesToConfiguredSpringApplicationWithoutStartingARealContext() {
        String[] args = {"--spring.main.banner-mode=off"};
        SpringApplication application = mock(SpringApplication.class);
        java.util.function.Function<String, SpringApplication> original =
                RvPortBackendApplication.applicationFactory;

        try {
            RvPortBackendApplication.applicationFactory = ignored -> application;
            RvPortBackendApplication.main(args);
        } finally {
            RvPortBackendApplication.applicationFactory = original;
        }

        verify(application).run(args);
        assertThat(new RvPortBackendApplication()).isNotNull();
    }
}
