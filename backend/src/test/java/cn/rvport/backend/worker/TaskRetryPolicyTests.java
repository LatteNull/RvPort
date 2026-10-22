package cn.rvport.backend.worker;

import static org.assertj.core.api.Assertions.assertThat;

import cn.rvport.backend.task.TaskErrorCode;
import org.junit.jupiter.api.Test;

class TaskRetryPolicyTests {

    private final TaskRetryPolicy policy = new TaskRetryPolicy();

    @Test
    void analysisProtocolAndBudgetFailuresAreNotRetried() {
        assertThat(policy.shouldRetry(TaskErrorCode.ANALYSIS_NON_RETRYABLE)).isFalse();
    }

    @Test
    void analysisTransientResourceFailuresRemainRetryable() {
        assertThat(policy.shouldRetry(TaskErrorCode.ANALYSIS_RETRYABLE_RESOURCE)).isTrue();
    }
}
