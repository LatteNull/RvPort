package cn.rvport.backend.config;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.core.env.StandardEnvironment;
import org.springframework.util.unit.DataSize;

class MultipartOverridePropertiesTests {

    @Test
    void overridesMultipartUploadLimitsFromEnvironmentProperties() {
        StandardEnvironment environment = ApplicationYamlTestSupport.environment(Map.of(
                "RVPORT_MAX_FILE_SIZE", "512MB",
                "RVPORT_MAX_REQUEST_SIZE", "768MB"
        ));

        assertThat(DataSize.parse(environment.getRequiredProperty("spring.servlet.multipart.max-file-size")))
                .isEqualTo(DataSize.ofMegabytes(512));
        assertThat(DataSize.parse(environment.getRequiredProperty("spring.servlet.multipart.max-request-size")))
                .isEqualTo(DataSize.ofMegabytes(768));
    }
}
