package cn.rvport.backend.dependency;

import java.util.Map;

public record DependencyAnalysisArtifactDetailResponse(
        DependencyAnalysisArtifactResponse artifact,
        Object content
) {
}
