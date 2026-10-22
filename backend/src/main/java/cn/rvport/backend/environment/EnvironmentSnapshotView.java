package cn.rvport.backend.environment;

import cn.rvport.backend.jooq.tables.records.EnvironmentSnapshotsRecord;
import cn.rvport.backend.task.TaskStatus;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public record EnvironmentSnapshotView(
        UUID id,
        UUID environmentId,
        UUID projectId,
        UUID taskId,
        long environmentConfigVersion,
        String osName,
        String osVersion,
        String kernelVersion,
        String arch,
        String packageManager,
        String snapshotKind,
        TaskStatus status,
        OffsetDateTime collectedAt
) {
    private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper();
    private static final TypeReference<Map<String, Object>> MAP_TYPE = new TypeReference<>() {
    };

    public static EnvironmentSnapshotView from(EnvironmentSnapshotsRecord record) {
        return new EnvironmentSnapshotView(
                record.getId(),
                record.getEnvironmentId(),
                record.getProjectId(),
                record.getTaskId(),
                record.getEnvironmentConfigVersion() == null ? 1L : record.getEnvironmentConfigVersion(),
                record.getOsName(),
                record.getOsVersion(),
                record.getKernelVersion(),
                record.getArch(),
                record.getPackageManager(),
                snapshotKind(record),
                TaskStatus.valueOf(record.getStatus()),
                record.getCollectedAt()
        );
    }

    public EnvironmentSnapshotView(
            UUID id,
            UUID environmentId,
            UUID projectId,
            UUID taskId,
            String osName,
            String osVersion,
            String kernelVersion,
            String arch,
            String packageManager,
            String snapshotKind,
            TaskStatus status,
            OffsetDateTime collectedAt
    ) {
        this(id, environmentId, projectId, taskId, 1L, osName, osVersion, kernelVersion, arch, packageManager,
                snapshotKind, status, collectedAt);
    }

    private static String snapshotKind(EnvironmentSnapshotsRecord record) {
        if (record.getRawSnapshot() == null || record.getRawSnapshot().data() == null) {
            return "FULL_COLLECT";
        }
        try {
            Map<String, Object> raw = OBJECT_MAPPER.readValue(record.getRawSnapshot().data(), MAP_TYPE);
            Object value = raw.get("snapshotKind");
            return value == null || value.toString().isBlank() ? "FULL_COLLECT" : value.toString();
        } catch (JsonProcessingException ex) {
            return "FULL_COLLECT";
        }
    }
}
