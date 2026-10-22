package cn.rvport.backend.automatedtest;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

public record AutomatedTestReportTarget(
        @NotNull AutomatedTestReportTargetType type,
        @NotBlank String path
) {
}
