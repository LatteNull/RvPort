package cn.rvport.backend.dependency;

import java.util.UUID;

public record DependencyAnalysisCreateRequest(
        UUID sourceRevisionId
) {
}
