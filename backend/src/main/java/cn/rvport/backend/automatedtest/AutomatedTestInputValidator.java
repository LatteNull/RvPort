package cn.rvport.backend.automatedtest;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.common.EnvironmentVariableValidator;
import java.nio.file.InvalidPathException;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;

@Component
public class AutomatedTestInputValidator {

    private static final int MAX_REPORT_TARGETS = 20;
    private final EnvironmentVariableValidator environmentVariableValidator;

    public AutomatedTestInputValidator() {
        this(new EnvironmentVariableValidator());
    }

    public AutomatedTestInputValidator(EnvironmentVariableValidator environmentVariableValidator) {
        this.environmentVariableValidator = environmentVariableValidator;
    }

    public Map<String, String> validateEnvironmentVariables(Map<String, String> variables) {
        return environmentVariableValidator.validate(variables, "TEST");
    }

    public Map<String, String> maskedEnvironmentVariables(Map<String, String> variables) {
        return environmentVariableValidator.mask(variables);
    }

    public List<AutomatedTestReportTarget> validateReportTargets(List<AutomatedTestReportTarget> targets) {
        if (targets == null || targets.isEmpty()) {
            return List.of();
        }
        if (targets.size() > MAX_REPORT_TARGETS) {
            throw badRequest("TEST_REPORT_TARGET_TOO_MANY", "报告目标数量过多");
        }
        return targets.stream()
                .map(target -> {
                    if (target == null || target.type() == null || target.path() == null || target.path().isBlank()) {
                        throw badRequest("TEST_REPORT_TARGET_INVALID", "报告目标不完整");
                    }
                    String path = normalizeRelativePath(target.path());
                    return new AutomatedTestReportTarget(target.type(), path);
                })
                .toList();
    }

    public String normalizeRelativePath(String value) {
        try {
            Path path = Path.of(value.trim()).normalize();
            if (path.isAbsolute() || path.toString().isBlank() || path.startsWith("..")) {
                throw badRequest("TEST_REPORT_PATH_INVALID", "报告路径必须是安全的相对路径");
            }
            String normalized = path.toString().replace('\\', '/');
            if (normalized.equals(".") || normalized.contains("/../") || normalized.startsWith("../")) {
                throw badRequest("TEST_REPORT_PATH_INVALID", "报告路径必须是安全的相对路径");
            }
            return normalized;
        } catch (InvalidPathException ex) {
            throw badRequest("TEST_REPORT_PATH_INVALID", "报告路径非法");
        }
    }

    private ApiException badRequest(String code, String message) {
        return new ApiException(HttpStatus.BAD_REQUEST, code, message);
    }
}
