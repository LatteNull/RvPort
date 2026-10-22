package cn.rvport.backend.user;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.common.error.ApiException;
import org.junit.jupiter.api.Test;

class PasswordPolicyTests {

    private final PasswordPolicy passwordPolicy = new PasswordPolicy();

    @Test
    void acceptsPasswordWithUppercaseLowercaseAndDigit() {
        assertThatCode(() -> passwordPolicy.validate("developer", "DevPass123"))
                .doesNotThrowAnyException();
    }

    @Test
    void rejectsPasswordWithoutUppercase() {
        assertThatThrownBy(() -> passwordPolicy.validate("developer", "devpass123"))
                .isInstanceOf(ApiException.class)
                .hasMessageContaining("密码至少 8 位");
    }

    @Test
    void rejectsPasswordWithoutLowercase() {
        assertThatThrownBy(() -> passwordPolicy.validate("developer", "DEVPASS123"))
                .isInstanceOf(ApiException.class);
    }

    @Test
    void rejectsPasswordWithoutDigit() {
        assertThatThrownBy(() -> passwordPolicy.validate("developer", "DevPassword"))
                .isInstanceOf(ApiException.class);
    }

    @Test
    void rejectsShortPassword() {
        assertThatThrownBy(() -> passwordPolicy.validate("developer", "Dev123"))
                .isInstanceOf(ApiException.class);
    }

    @Test
    void rejectsNullPasswordWithAllMissingRequirements() {
        assertThatThrownBy(() -> passwordPolicy.validate("developer", null))
                .isInstanceOfSatisfying(ApiException.class, failure ->
                        org.assertj.core.api.Assertions.assertThat(failure.details().get("reasons"))
                                .asList().containsExactly("length", "uppercase", "lowercase", "digit"));
    }

    @Test
    void rejectsPasswordEqualToUsernameIgnoringCase() {
        assertThatThrownBy(() -> passwordPolicy.validate("DevPass123", "devpass123"))
                .isInstanceOfSatisfying(ApiException.class, failure ->
                        org.assertj.core.api.Assertions.assertThat(failure.details().get("reasons"))
                                .asList().contains("same_as_username"));
        assertThatCode(() -> passwordPolicy.validate(null, "DevPass123")).doesNotThrowAnyException();
    }
}
