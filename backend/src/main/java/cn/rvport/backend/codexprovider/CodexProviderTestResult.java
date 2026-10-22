package cn.rvport.backend.codexprovider;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public record CodexProviderTestResult(
        boolean success,
        String status,
        String message,
        Instant testedAt,
        String agentType,
        UUID agentRuntimeId,
        boolean basicAvailable,
        boolean agentCompatible,
        List<CodexProviderProbeCheckResult> checks,
        Map<String, Object> details
) {
    public static CodexProviderTestResult success(String message, Instant testedAt) {
        return new CodexProviderTestResult(true, CodexProviderTestStatus.SUCCESS.name(), message, testedAt,
                AgentType.CODEX.name(), null, true, true, List.of(), Map.of());
    }

    public static CodexProviderTestResult failure(String message, Instant testedAt) {
        return new CodexProviderTestResult(false, CodexProviderTestStatus.FAILED.name(), message, testedAt,
                AgentType.CODEX.name(), null, false, false, List.of(), Map.of());
    }

    public static CodexProviderTestResult failure(String message, Instant testedAt, AgentType agentType, UUID agentRuntimeId) {
        return new CodexProviderTestResult(false, CodexProviderTestStatus.FAILED.name(), message, testedAt,
                agentType.name(), agentRuntimeId, false, false, List.of(), Map.of(
                "agentType", agentType.name(),
                "agentRuntimeId", agentRuntimeId
        ));
    }

    public static CodexProviderTestResult of(
            boolean success,
            String message,
            Instant testedAt,
            AgentType agentType,
            UUID agentRuntimeId,
            boolean basicAvailable,
            boolean agentCompatible,
            List<CodexProviderProbeCheckResult> checks
    ) {
        return new CodexProviderTestResult(
                success,
                success ? CodexProviderTestStatus.SUCCESS.name() : CodexProviderTestStatus.FAILED.name(),
                message,
                testedAt,
                agentType.name(),
                agentRuntimeId,
                basicAvailable,
                agentCompatible,
                checks == null ? List.of() : List.copyOf(checks),
                Map.of(
                        "agentType", agentType.name(),
                        "agentRuntimeId", agentRuntimeId,
                        "checks", checks == null ? List.of() : List.copyOf(checks),
                        "capabilities", Map.of(
                                "basicAvailable", basicAvailable,
                                "agentCompatible", agentCompatible
                        )
                )
        );
    }
}
