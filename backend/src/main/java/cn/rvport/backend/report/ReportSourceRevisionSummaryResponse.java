package cn.rvport.backend.report;

import cn.rvport.backend.source.SourceRevisionType;
import cn.rvport.backend.source.SourceRevisionView;
import java.time.OffsetDateTime;
import java.util.UUID;

public record ReportSourceRevisionSummaryResponse(
        UUID id,
        UUID projectId,
        SourceRevisionType revisionType,
        String versionLabel,
        String gitBranch,
        String gitCommit,
        boolean active,
        OffsetDateTime createdAt
) {
    public static ReportSourceRevisionSummaryResponse from(SourceRevisionView view) {
        if (view == null) {
            return null;
        }
        return new ReportSourceRevisionSummaryResponse(
                view.id(),
                view.projectId(),
                view.revisionType(),
                view.versionLabel(),
                view.gitBranch(),
                view.gitCommit(),
                view.active(),
                view.createdAt()
        );
    }
}
