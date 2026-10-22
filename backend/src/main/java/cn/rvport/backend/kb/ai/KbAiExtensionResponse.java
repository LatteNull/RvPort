package cn.rvport.backend.kb.ai;

import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record KbAiExtensionResponse(
        UUID id,
        UUID projectId,
        UUID sourceRevisionId,
        UUID kbScanRunId,
        UUID taskId,
        UUID modelProfileId,
        UUID agentRuntimeId,
        String status,
        Map<String, Object> summary,
        UUID inputArtifactId,
        UUID outputArtifactId,
        UUID agentOutputArtifactId,
        OffsetDateTime startedAt,
        OffsetDateTime finishedAt,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
    static KbAiExtensionResponse from(KbAiExtensionRunView view) {
        return new KbAiExtensionResponse(
                view.id(),
                view.projectId(),
                view.sourceRevisionId(),
                view.kbScanRunId(),
                view.taskId(),
                view.modelProfileId(),
                view.agentRuntimeId(),
                view.status().name(),
                view.summary(),
                view.inputArtifactId(),
                view.outputArtifactId(),
                view.agentOutputArtifactId(),
                view.startedAt(),
                view.finishedAt(),
                view.createdAt(),
                view.updatedAt()
        );
    }
}
