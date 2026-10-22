package cn.rvport.backend.automatedtest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.common.EnvironmentVariableValidator;
import cn.rvport.backend.common.error.ApiException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class AutomatedTestInputValidatorTests {

    private final AutomatedTestInputValidator validator = new AutomatedTestInputValidator();

    @Test
    void delegatesEnvironmentValidationAndMasking() {
        assertThat(validator.validateEnvironmentVariables(Map.of("MODE", "test")))
                .containsEntry("MODE", "test");
        assertThat(validator.maskedEnvironmentVariables(Map.of("API_TOKEN", "secret")))
                .containsEntry("API_TOKEN", "****");
        assertThat(new AutomatedTestInputValidator(new EnvironmentVariableValidator())
                .validateEnvironmentVariables(null)).isEmpty();
    }

    @Test
    void normalizesValidReportFilesAndDirectoriesAndHandlesEmptyInput() {
        assertThat(validator.validateReportTargets(null)).isEmpty();
        assertThat(validator.validateReportTargets(List.of())).isEmpty();
        assertThat(validator.validateReportTargets(List.of(
                new AutomatedTestReportTarget(AutomatedTestReportTargetType.FILE, " reports/../reports/result.xml "),
                new AutomatedTestReportTarget(AutomatedTestReportTargetType.DIRECTORY, "reports\\html")
        ))).extracting(AutomatedTestReportTarget::path)
                .containsExactly("reports/result.xml", "reports/html");
    }

    @Test
    void rejectsTooManyIncompleteAndUnsafeReportTargets() {
        List<AutomatedTestReportTarget> tooMany = new ArrayList<>();
        for (int i = 0; i < 21; i++) {
            tooMany.add(new AutomatedTestReportTarget(AutomatedTestReportTargetType.FILE, "r" + i));
        }
        assertCode(() -> validator.validateReportTargets(tooMany), "TEST_REPORT_TARGET_TOO_MANY");
        assertCode(() -> validator.validateReportTargets(java.util.Arrays.asList((AutomatedTestReportTarget) null)),
                "TEST_REPORT_TARGET_INVALID");
        assertCode(() -> validator.validateReportTargets(List.of(new AutomatedTestReportTarget(null, "a"))),
                "TEST_REPORT_TARGET_INVALID");
        assertCode(() -> validator.validateReportTargets(List.of(
                new AutomatedTestReportTarget(AutomatedTestReportTargetType.FILE, null))), "TEST_REPORT_TARGET_INVALID");
        assertCode(() -> validator.validateReportTargets(List.of(
                new AutomatedTestReportTarget(AutomatedTestReportTargetType.FILE, " "))), "TEST_REPORT_TARGET_INVALID");
        assertCode(() -> validator.normalizeRelativePath("../secret"), "TEST_REPORT_PATH_INVALID");
        assertCode(() -> validator.normalizeRelativePath("."), "TEST_REPORT_PATH_INVALID");
        assertCode(() -> validator.normalizeRelativePath("/absolute/report"), "TEST_REPORT_PATH_INVALID");
        assertCode(() -> validator.normalizeRelativePath("bad\u0000path"), "TEST_REPORT_PATH_INVALID");
    }

    private void assertCode(org.assertj.core.api.ThrowableAssert.ThrowingCallable call, String code) {
        assertThatThrownBy(call).isInstanceOfSatisfying(ApiException.class,
                failure -> assertThat(failure.code()).isEqualTo(code));
    }
}
