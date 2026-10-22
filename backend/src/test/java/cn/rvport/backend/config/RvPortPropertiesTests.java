package cn.rvport.backend.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.springframework.core.env.StandardEnvironment;
import org.springframework.util.unit.DataSize;

class RvPortPropertiesTests {

    @Test
    void bindsRuntimeProperties() {
        RvPortProperties properties = properties();

        assertThat(properties.runtime().logDir()).isNotBlank();
        assertThat(properties.runtime().archiveDir()).isNotBlank();
        assertThat(properties.runtime().uploadDir()).isNotBlank();
    }

    @Test
    void bindsKbScanProperties() {
        RvPortProperties properties = properties();

        assertThat(properties.kbScan().pythonCommand()).isNotBlank();
        assertThat(properties.kbScan().scannerRoot()).isNotBlank();
        assertThat(properties.kbScan().rulesetPath()).isNotBlank();
        assertThat(properties.kbScan().outputDir()).isNotBlank();
        assertThat(properties.kbScan().timeoutSeconds()).isPositive();
        assertThat(properties.kbScan().language()).isEqualTo("c,cpp");
        assertThat(properties.kbScan().targetArch()).isEqualTo("riscv64");
        assertThat(properties.kbScan().contextLines()).isEqualTo(20);
    }

    @Test
    void bindsDefaultMultipartUploadLimitsToTenGb() {
        StandardEnvironment environment = ApplicationYamlTestSupport.environment();

        assertThat(DataSize.parse(environment.getRequiredProperty("spring.servlet.multipart.max-file-size")))
                .isEqualTo(DataSize.ofGigabytes(10));
        assertThat(DataSize.parse(environment.getRequiredProperty("spring.servlet.multipart.max-request-size")))
                .isEqualTo(DataSize.ofGigabytes(10));
    }

    @Test
    void bindsBitcodeDefaultsAndRejectsUnsafeConfiguration() {
        RvPortProperties.Bitcode bitcode = properties().bitcode();

        assertThat(bitcode.enabled()).isTrue();
        assertThat(bitcode.toolchainVersion()).isEqualTo("21.1.8");
        assertThat(bitcode.bundleSha256()).hasSize(64);
        assertThat(bitcode.maxTranslationUnits()).isPositive();
        assertThat(bitcode.maxBundleBytes()).isPositive();

        assertThatThrownBy(() -> new RvPortProperties.Bitcode(true, "id", "21", "bundle", "bad",
                ".rvport/toolchains", 1, 1L, 1L, 1, 1, 1))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("SHA-256");
        assertThatThrownBy(() -> new RvPortProperties.Bitcode(true, "id", "21", "bundle", "a".repeat(64),
                "../escape", 1, 1L, 1L, 1, 1, 1))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("安全相对路径");
    }

    private RvPortProperties properties() {
        StandardEnvironment environment = ApplicationYamlTestSupport.environment();
        return ApplicationYamlTestSupport.bind(environment, "rvport", RvPortProperties.class);
    }
}
