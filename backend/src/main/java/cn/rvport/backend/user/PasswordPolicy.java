package cn.rvport.backend.user;

import cn.rvport.backend.common.error.ApiException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;

@Component
public class PasswordPolicy {

    public void validate(String username, String password) {
        List<String> reasons = new ArrayList<>();
        if (password == null || password.length() < 8) {
            reasons.add("length");
        }
        if (password == null || password.chars().noneMatch(Character::isUpperCase)) {
            reasons.add("uppercase");
        }
        if (password == null || password.chars().noneMatch(Character::isLowerCase)) {
            reasons.add("lowercase");
        }
        if (password == null || password.chars().noneMatch(Character::isDigit)) {
            reasons.add("digit");
        }
        if (username != null && password != null && username.equalsIgnoreCase(password)) {
            reasons.add("same_as_username");
        }
        if (!reasons.isEmpty()) {
            throw new ApiException(
                    HttpStatus.BAD_REQUEST,
                    "PASSWORD_POLICY_FAILED",
                    "密码至少 8 位，并且必须包含大写字母、小写字母和数字",
                    Map.of("reasons", reasons)
            );
        }
    }
}
