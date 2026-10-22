package cn.rvport.backend.dependency;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import java.util.UUID;

@JsonIgnoreProperties(ignoreUnknown = true)
public record DependencyAnalysisTaskInput(
        UUID projectId,
        UUID analysisRunId,
        UUID sourceRevisionId,
        UUID sourceBuildRunId,
        UUID targetEnvironmentId,
        Long environmentConfigVersion
) {
}
