package cn.rvport.backend.automatedtest;

import cn.rvport.backend.common.error.ApiException;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class AutomatedTestInputValidatorTest {

    private final AutomatedTestInputValidator validator = new AutomatedTestInputValidator();

    @Test
    void acceptsNormalEnvironmentVariablesAndReportTargets() {
        Map<String, String> variables = validator.validateEnvironmentVariables(Map.of(
                "CC", "gcc",
                "RVPORT_TEST_FLAG", "1"
        ));
        List<AutomatedTestReportTarget> targets = validator.validateReportTargets(List.of(
                new AutomatedTestReportTarget(AutomatedTestReportTargetType.FILE, "reports/result.txt"),
                new AutomatedTestReportTarget(AutomatedTestReportTargetType.DIRECTORY, "reports/html")
        ));

        assertThat(variables).containsEntry("CC", "gcc");
        assertThat(targets).extracting(AutomatedTestReportTarget::path)
                .containsExactly("reports/result.txt", "reports/html");
    }

    @Test
    void rejectsInvalidEnvironmentVariableNameAndUnsafeReportPath() {
        assertThatThrownBy(() -> validator.validateEnvironmentVariables(Map.of("1BAD", "value")))
                .isInstanceOf(ApiException.class)
                .hasMessageContaining("环境变量名称非法");

        assertThatThrownBy(() -> validator.validateReportTargets(List.of(
                new AutomatedTestReportTarget(AutomatedTestReportTargetType.FILE, "../secret.txt")
        )))
                .isInstanceOf(ApiException.class)
                .hasMessageContaining("报告路径必须是安全的相对路径");
    }

    @Test
    void masksSensitiveEnvironmentVariablesAndNormalizesEdgeCasePaths() {
        Map<String, String> masked = validator.maskedEnvironmentVariables(Map.of(
                "API_TOKEN", "secret-token",
                "NORMAL_VALUE", "visible"
        ));
        String path = validator.normalizeRelativePath("reports/./summary.txt");

        assertThat(masked).containsEntry("API_TOKEN", "****")
                .containsEntry("NORMAL_VALUE", "visible");
        assertThat(path).isEqualTo("reports/summary.txt");
    }
}
