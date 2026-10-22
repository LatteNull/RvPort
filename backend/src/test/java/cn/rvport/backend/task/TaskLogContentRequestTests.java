package cn.rvport.backend.task;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.common.error.ApiException;
import java.util.List;
import org.junit.jupiter.api.Test;

class TaskLogContentRequestTests {

    @Test
    void defaultsToAllLogTypesWithSharedPageSize() {
        TaskLogContentRequest request = TaskLogContentRequest.from(null, null,
                null, null, null, null, null, null);

        assertThat(request.entries()).extracting(TaskLogContentRequest.Entry::type)
                .containsExactly("merged", "stdout", "stderr");
        assertThat(request.entries()).extracting(TaskLogContentRequest.Entry::logType)
                .containsExactly(TaskLogType.COMBINED, TaskLogType.STDOUT, TaskLogType.STDERR);
        assertThat(request.entries()).allSatisfy(entry -> {
            assertThat(entry.offset()).isZero();
            assertThat(entry.lines()).isEqualTo(100);
        });
    }

    @Test
    void normalizesCaseWhitespaceDuplicatesAndIndependentPaging() {
        TaskLogContentRequest request = TaskLogContentRequest.from(" STDOUT,merged,stdout, ,StDeRr ", 50,
                2L, 3L, 4L, 20, 30, 40);

        assertThat(request.entries()).containsExactly(
                new TaskLogContentRequest.Entry("stdout", TaskLogType.STDOUT, 3, 30),
                new TaskLogContentRequest.Entry("merged", TaskLogType.COMBINED, 2, 20),
                new TaskLogContentRequest.Entry("stderr", TaskLogType.STDERR, 4, 40)
        );
    }

    @Test
    void usesSharedLinesWhenPerTypeValuesAreAbsentAndAcceptsBounds() {
        TaskLogContentRequest zero = TaskLogContentRequest.from("merged", 0,
                0L, null, null, null, null, null);
        TaskLogContentRequest max = TaskLogContentRequest.from("stderr", 5000,
                null, null, 1L, null, null, null);

        assertThat(zero.entries().getFirst().lines()).isZero();
        assertThat(max.entries().getFirst()).isEqualTo(
                new TaskLogContentRequest.Entry("stderr", TaskLogType.STDERR, 1, 5000));
    }

    @Test
    void rejectsUnknownOrEffectivelyEmptyTypes() {
        assertInvalid("TASK_LOG_TYPE_INVALID", () -> TaskLogContentRequest.from("trace", 1,
                null, null, null, null, null, null));
        assertInvalid("TASK_LOG_TYPE_INVALID", () -> TaskLogContentRequest.from(" , , ", 1,
                null, null, null, null, null, null));
    }

    @Test
    void rejectsNegativeOffsetsForEveryLogType() {
        List<Runnable> actions = List.of(
                () -> TaskLogContentRequest.from("merged", 1, -1L, null, null, null, null, null),
                () -> TaskLogContentRequest.from("stdout", 1, null, -1L, null, null, null, null),
                () -> TaskLogContentRequest.from("stderr", 1, null, null, -1L, null, null, null)
        );
        actions.forEach(action -> assertInvalid("TASK_LOG_OFFSET_INVALID", action));
    }

    @Test
    void rejectsNegativeOrOversizedSharedAndPerTypeLineCounts() {
        assertInvalid("TASK_LOG_LINES_INVALID", () -> TaskLogContentRequest.from(null, -1,
                null, null, null, null, null, null));
        assertInvalid("TASK_LOG_LINES_INVALID", () -> TaskLogContentRequest.from(null, 5001,
                null, null, null, null, null, null));
        assertInvalid("TASK_LOG_LINES_INVALID", () -> TaskLogContentRequest.from("merged", 1,
                null, null, null, -1, null, null));
        assertInvalid("TASK_LOG_LINES_INVALID", () -> TaskLogContentRequest.from("stdout", 1,
                null, null, null, null, 5001, null));
        assertInvalid("TASK_LOG_LINES_INVALID", () -> TaskLogContentRequest.from("stderr", 1,
                null, null, null, null, null, -1));
    }

    @Test
    void perTypeLineCountsOverrideSharedValueForEveryLogType() {
        TaskLogContentRequest request = TaskLogContentRequest.from(
                "merged,stdout,stderr", 5, null, null, null, 11, 12, 13);

        assertThat(request.entries()).extracting(TaskLogContentRequest.Entry::lines)
                .containsExactly(11, 12, 13);
    }

    private void assertInvalid(String code, Runnable action) {
        assertThatThrownBy(action::run)
                .isInstanceOf(ApiException.class)
                .extracting("code")
                .isEqualTo(code);
    }
}
