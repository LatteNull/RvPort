package cn.rvport.backend.automatedtest;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Positive;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public record AutomatedTestRequest(
        UUID buildRunId,
        UUID sourceRevisionId,
        UUID environmentId,
        UUID testBatchId,
        TestBatchRole testBatchRole,
        @NotBlank String command,
        String workingDirectory,
        @Positive Integer timeoutSeconds,
        Map<String, String> environmentVariables,
        @Valid List<AutomatedTestReportTarget> reportTargets
) {
}
