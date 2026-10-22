package cn.rvport.backend.codexprovider;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class CodexProviderResultTests {

    @Test
    void processResultSelectsFirstMeaningfulOutput() {
        assertThat(new CodexProcessResult(0, false, "stdout", "stderr").mergedOutput()).isEqualTo("stdout");
        assertThat(new CodexProcessResult(0, false, null, "stderr").mergedOutput()).isEqualTo("stderr");
        assertThat(new CodexProcessResult(0, false, " ", "stderr").mergedOutput()).isEqualTo("stderr");
        assertThat(new CodexProcessResult(0, false, "", null).mergedOutput()).isEmpty();
        assertThat(new CodexProcessResult(0, false, "", " ").mergedOutput()).isEmpty();
    }

    @Test
    void providerResultFactoriesExposeConsistentCapabilitiesAndDetails() {
        Instant testedAt = Instant.parse("2026-09-12T00:00:00Z");
        UUID runtimeId = UUID.randomUUID();
        var check = CodexProviderProbeCheckResult.failure(CodexProviderProbeName.AGENT_TEXT,
                "FAILED", "bad", 12);

        CodexProviderTestResult success = CodexProviderTestResult.success("ok", testedAt);
        assertThat(success.success()).isTrue();
        assertThat(success.checks()).isEmpty();

        CodexProviderTestResult simpleFailure = CodexProviderTestResult.failure("bad", testedAt);
        assertThat(simpleFailure.success()).isFalse();
        assertThat(simpleFailure.agentType()).isEqualTo("CODEX");

        CodexProviderTestResult runtimeFailure = CodexProviderTestResult.failure(
                "bad", testedAt, AgentType.OPENCODE, runtimeId);
        assertThat(runtimeFailure.details()).containsEntry("agentType", "OPENCODE")
                .containsEntry("agentRuntimeId", runtimeId);

        CodexProviderTestResult nullChecks = CodexProviderTestResult.of(false, "bad", testedAt,
                AgentType.DEEPSEEK_HARNESS, runtimeId, true, false, null);
        assertThat(nullChecks.status()).isEqualTo("FAILED");
        assertThat(nullChecks.checks()).isEmpty();
        @SuppressWarnings("unchecked")
        java.util.Map<String, Object> capabilities =
                (java.util.Map<String, Object>) nullChecks.details().get("capabilities");
        assertThat(capabilities).containsEntry("basicAvailable", true).containsEntry("agentCompatible", false);

        CodexProviderTestResult checks = CodexProviderTestResult.of(true, "ok", testedAt,
                AgentType.CODEX, runtimeId, true, true, List.of(check));
        assertThat(checks.status()).isEqualTo("SUCCESS");
        assertThat(checks.checks()).containsExactly(check);
        assertThat(checks.details().get("checks")).isEqualTo(List.of(check));
    }
}
