package cn.rvport.backend.project;

import java.time.OffsetDateTime;
import java.util.UUID;

public record ProjectResponse(
        UUID id,
        String name,
        String description,
        String sourceArch,
        String targetArch,
        ProjectStage stage,
        ProjectStatus status,
        ProjectSourceInputType sourceInputType,
        UUID createdBy,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt,
        long highRiskCount,
        OffsetDateTime latestScanAt,
        String latestBuildStatus,
        String latestTestStatus
) {
    public static ProjectResponse from(ProjectView view) {
        return from(view, ProjectSummaryView.empty());
    }

    public static ProjectResponse from(ProjectView view, ProjectSummaryView summary) {
        return new ProjectResponse(
                view.id(),
                view.name(),
                view.description(),
                view.sourceArch(),
                view.targetArch(),
                view.stage(),
                view.status(),
                view.sourceInputType(),
                view.createdBy(),
                view.createdAt(),
                view.updatedAt(),
                summary.highRiskCount(),
                summary.latestScanAt(),
                summary.latestBuildStatus(),
                summary.latestTestStatus()
        );
    }
}
