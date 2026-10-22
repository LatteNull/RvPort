package cn.rvport.backend.task;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.common.error.ApiException;
import org.junit.jupiter.api.Test;

class TaskLogIncrementRequestTests {

    @Test
    void usesDefaultsAndAcceptsValidValues() {
        assertThat(TaskLogIncrementRequest.from(null, null))
                .isEqualTo(new TaskLogIncrementRequest(0, 500));
        assertThat(TaskLogIncrementRequest.from(" 42 ", "1000"))
                .isEqualTo(new TaskLogIncrementRequest(42, 1000));
    }

    @Test
    void rejectsInvalidCursorAndLimit() {
        assertCode(() -> TaskLogIncrementRequest.from("-1", null), "TASK_LOG_EVENT_CURSOR_INVALID");
        assertCode(() -> TaskLogIncrementRequest.from("bad", null), "TASK_LOG_EVENT_CURSOR_INVALID");
        assertCode(() -> TaskLogIncrementRequest.from(null, "0"), "TASK_LOG_EVENT_LIMIT_INVALID");
        assertCode(() -> TaskLogIncrementRequest.from(null, "1001"), "TASK_LOG_EVENT_LIMIT_INVALID");
        assertCode(() -> TaskLogIncrementRequest.from(null, "999999999999"), "TASK_LOG_EVENT_LIMIT_INVALID");
    }

    private void assertCode(Runnable action, String code) {
        assertThatThrownBy(action::run)
                .isInstanceOf(ApiException.class)
                .extracting(ex -> ((ApiException) ex).code())
                .isEqualTo(code);
    }
}
