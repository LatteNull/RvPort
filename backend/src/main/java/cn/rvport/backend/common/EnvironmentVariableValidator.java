package cn.rvport.backend.common;

import cn.rvport.backend.common.error.ApiException;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;

@Component
public class EnvironmentVariableValidator {

    private static final int MAX_ENV_VARS = 64;
    private static final int MAX_ENV_VALUE_LENGTH = 4096;
    private static final int MAX_ENV_TOTAL_LENGTH = 65536;

    public Map<String, String> validate(Map<String, String> variables, String codePrefix) {
        if (variables == null || variables.isEmpty()) {
            return Map.of();
        }
        if (variables.size() > MAX_ENV_VARS) {
            throw badRequest(codePrefix + "_ENV_TOO_MANY", "环境变量数量过多");
        }
        Map<String, String> result = new LinkedHashMap<>();
        int totalLength = 0;
        for (Map.Entry<String, String> entry : variables.entrySet()) {
            String name = entry.getKey();
            String value = entry.getValue() == null ? "" : entry.getValue();
            if (name == null || !name.matches("[A-Za-z_][A-Za-z0-9_]*")) {
                throw badRequest(codePrefix + "_ENV_NAME_INVALID", "环境变量名称非法");
            }
            if (value.length() > MAX_ENV_VALUE_LENGTH) {
                throw badRequest(codePrefix + "_ENV_VALUE_TOO_LONG", "环境变量值过长");
            }
            totalLength += name.length() + value.length();
            if (totalLength > MAX_ENV_TOTAL_LENGTH) {
                throw badRequest(codePrefix + "_ENV_TOO_LARGE", "环境变量总大小过大");
            }
            result.put(name, value);
        }
        return result;
    }

    public Map<String, String> mask(Map<String, String> variables) {
        if (variables == null || variables.isEmpty()) {
            return Map.of();
        }
        Map<String, String> result = new LinkedHashMap<>();
        variables.forEach((name, value) -> result.put(name, sensitiveName(name) ? "****" : value));
        return result;
    }

    private boolean sensitiveName(String name) {
        String upper = name == null ? "" : name.toUpperCase(Locale.ROOT);
        return upper.contains("TOKEN")
                || upper.contains("PASSWORD")
                || upper.contains("PASS")
                || upper.contains("SECRET")
                || upper.contains("KEY");
    }

    private ApiException badRequest(String code, String message) {
        return new ApiException(HttpStatus.BAD_REQUEST, code, message);
    }
}
