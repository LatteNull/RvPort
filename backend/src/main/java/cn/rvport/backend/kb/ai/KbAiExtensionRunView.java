package cn.rvport.backend.kb.ai;

import cn.rvport.backend.jooq.tables.records.KbAiExtensionRunsRecord;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record KbAiExtensionRunView(
        UUID id,
        UUID projectId,
        UUID sourceRevisionId,
        UUID kbScanRunId,
        UUID taskId,
        UUID modelProfileId,
        UUID agentRuntimeId,
        KbAiExtensionStatus status,
        Map<String, Object> summary,
        UUID inputArtifactId,
        UUID outputArtifactId,
        UUID agentOutputArtifactId,
        UUID createdBy,
        OffsetDateTime startedAt,
        OffsetDateTime finishedAt,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
    static KbAiExtensionRunView from(KbAiExtensionRunsRecord record, Map<String, Object> summary) {
        return new KbAiExtensionRunView(
                record.getId(),
                record.getProjectId(),
                record.getSourceRevisionId(),
                record.getKbScanRunId(),
                record.getTaskId(),
                record.getModelProfileId(),
                record.getAgentRuntimeId(),
                KbAiExtensionStatus.valueOf(record.getStatus()),
                summary,
                record.getInputArtifactId(),
                record.getOutputArtifactId(),
                record.getAgentOutputArtifactId(),
                record.getCreatedBy(),
                record.getStartedAt(),
                record.getFinishedAt(),
                record.getCreatedAt(),
                record.getUpdatedAt()
        );
    }
}
