package cn.rvport.backend.common;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.common.error.ApiException;
import java.util.LinkedHashMap;
import java.util.Map;
import org.junit.jupiter.api.Test;

class EnvironmentVariableValidatorTests {

    private final EnvironmentVariableValidator validator = new EnvironmentVariableValidator();

    @Test
    void acceptsValidVariablesNormalizesNullValuesAndHandlesEmptyInput() {
        assertThat(validator.validate(null, "BUILD")).isEmpty();
        assertThat(validator.validate(Map.of(), "BUILD")).isEmpty();
        Map<String, String> input = new LinkedHashMap<>();
        input.put("PATH_1", "/bin");
        input.put("EMPTY", null);
        assertThat(validator.validate(input, "BUILD"))
                .containsEntry("PATH_1", "/bin")
                .containsEntry("EMPTY", "");
    }

    @Test
    void rejectsTooManyInvalidNamedAndOversizedVariablesWithStableCodes() {
        Map<String, String> tooMany = new LinkedHashMap<>();
        for (int i = 0; i < 65; i++) {
            tooMany.put("V" + i, "x");
        }
        assertCode(() -> validator.validate(tooMany, "TEST"), "TEST_ENV_TOO_MANY");
        assertCode(() -> validator.validate(java.util.Collections.singletonMap(null, "x"), "TEST"),
                "TEST_ENV_NAME_INVALID");
        assertCode(() -> validator.validate(Map.of("1INVALID", "x"), "TEST"), "TEST_ENV_NAME_INVALID");
        assertCode(() -> validator.validate(Map.of("VALID", "x".repeat(4097)), "TEST"),
                "TEST_ENV_VALUE_TOO_LONG");

        Map<String, String> tooLarge = new LinkedHashMap<>();
        for (int i = 0; i < 17; i++) {
            tooLarge.put("VALUE_" + i, "x".repeat(4096));
        }
        assertCode(() -> validator.validate(tooLarge, "TEST"), "TEST_ENV_TOO_LARGE");
    }

    @Test
    void masksEverySensitiveNameCaseInsensitivelyAndPreservesOrdinaryValues() {
        Map<String, String> values = new LinkedHashMap<>();
        values.put(null, "null-name");
        values.put("API_TOKEN", "a");
        values.put("dbPassword", "b");
        values.put("PASS_PHRASE", "c");
        values.put("client_secret", "d");
        values.put("SSH_KEY", "e");
        values.put("HOME", "/home/user");

        assertThat(validator.mask(values))
                .containsEntry(null, "null-name")
                .containsEntry("API_TOKEN", "****")
                .containsEntry("dbPassword", "****")
                .containsEntry("PASS_PHRASE", "****")
                .containsEntry("client_secret", "****")
                .containsEntry("SSH_KEY", "****")
                .containsEntry("HOME", "/home/user");
        assertThat(validator.mask(null)).isEmpty();
        assertThat(validator.mask(Map.of())).isEmpty();
    }

    private void assertCode(org.assertj.core.api.ThrowableAssert.ThrowingCallable call, String code) {
        assertThatThrownBy(call).isInstanceOfSatisfying(ApiException.class,
                failure -> assertThat(failure.code()).isEqualTo(code));
    }
}
