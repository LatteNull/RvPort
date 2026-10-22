package cn.rvport.backend.environment;

import static cn.rvport.backend.jooq.tables.EnvironmentSnapshots.ENVIRONMENT_SNAPSHOTS;
import static cn.rvport.backend.jooq.tables.Environments.ENVIRONMENTS;
import static cn.rvport.backend.jooq.tables.EnvironmentComponents.ENVIRONMENT_COMPONENTS;

import cn.rvport.backend.jooq.tables.records.EnvironmentsRecord;
import cn.rvport.backend.jooq.tables.records.EnvironmentComponentsRecord;
import cn.rvport.backend.task.TaskStatus;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.OffsetDateTime;
import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.jooq.Condition;
import org.jooq.DSLContext;
import org.jooq.Field;
import org.jooq.JSONB;
import org.jooq.Record;
import org.jooq.impl.DSL;
import org.springframework.stereotype.Repository;

@Repository
public class EnvironmentRepository {

    public static final Field<UUID> JUMP_HOST_ENVIRONMENT_ID = ENVIRONMENTS.JUMP_HOST_ENVIRONMENT_ID;
    private static final int COMPONENT_BATCH_SIZE = 1000;
    private static final TypeReference<Map<String, Object>> MAP_TYPE = new TypeReference<>() {
    };

    private final DSLContext dsl;
    private final ObjectMapper objectMapper;

    public EnvironmentRepository(DSLContext dsl, ObjectMapper objectMapper) {
        this.dsl = dsl;
        this.objectMapper = objectMapper;
    }

    public EnvironmentView create(
            UUID projectId,
            String name,
            EnvironmentRole role,
            String arch,
            String host,
            int sshPort,
            String username,
            UUID credentialId,
            UUID jumpHostEnvironmentId,
            String workingDirectory,
            UUID createdBy
    ) {
        EnvironmentsRecord record = dsl.insertInto(ENVIRONMENTS)
                .set(ENVIRONMENTS.PROJECT_ID, projectId)
                .set(ENVIRONMENTS.NAME, name)
                .set(ENVIRONMENTS.ROLE, role.name())
                .set(ENVIRONMENTS.ARCH, arch)
                .set(ENVIRONMENTS.HOST, host)
                .set(ENVIRONMENTS.SSH_PORT, sshPort)
                .set(ENVIRONMENTS.USERNAME, username)
                .set(ENVIRONMENTS.CREDENTIAL_ID, credentialId)
                .set(JUMP_HOST_ENVIRONMENT_ID, jumpHostEnvironmentId)
                .set(ENVIRONMENTS.WORKING_DIRECTORY, blankToNull(workingDirectory))
                .set(ENVIRONMENTS.STATUS, EnvironmentStatus.UNKNOWN.name())
                .set(ENVIRONMENTS.ENABLED, true)
                .set(ENVIRONMENTS.CREATED_BY, createdBy)
                .returning()
                .fetchOne();
        return findById(record.getId()).orElseThrow();
    }

    public Optional<EnvironmentView> findById(UUID environmentId) {
        return dsl.select(ENVIRONMENTS.fields())
                .from(ENVIRONMENTS)
                .where(ENVIRONMENTS.ID.eq(environmentId))
                .fetchOptional(this::map);
    }

    public long count(UUID projectId, EnvironmentRole role, EnvironmentStatus status, Boolean enabled) {
        return dsl.selectCount()
                .from(ENVIRONMENTS)
                .where(filter(projectId, role, status, enabled))
                .fetchOne(0, long.class);
    }

    public List<EnvironmentView> list(UUID projectId, EnvironmentRole role, EnvironmentStatus status, Boolean enabled, int page, int pageSize) {
        return dsl.select(ENVIRONMENTS.fields())
                .from(ENVIRONMENTS)
                .where(filter(projectId, role, status, enabled))
                .orderBy(ENVIRONMENTS.CREATED_AT.desc(), ENVIRONMENTS.NAME.asc())
                .limit(pageSize)
                .offset((page - 1) * pageSize)
                .fetch(this::map);
    }

    public EnvironmentView update(
            UUID environmentId,
            String name,
            EnvironmentRole role,
            String arch,
            String host,
            int sshPort,
            String username,
            UUID credentialId,
            UUID jumpHostEnvironmentId,
            String workingDirectory,
            boolean enabled,
            boolean effectiveConfigurationChanged
    ) {
        var update = dsl.update(ENVIRONMENTS)
                .set(ENVIRONMENTS.NAME, name)
                .set(ENVIRONMENTS.ROLE, role.name())
                .set(ENVIRONMENTS.ARCH, arch)
                .set(ENVIRONMENTS.HOST, host)
                .set(ENVIRONMENTS.SSH_PORT, sshPort)
                .set(ENVIRONMENTS.USERNAME, username)
                .set(ENVIRONMENTS.CREDENTIAL_ID, credentialId)
                .set(JUMP_HOST_ENVIRONMENT_ID, jumpHostEnvironmentId)
                .set(ENVIRONMENTS.WORKING_DIRECTORY, blankToNull(workingDirectory))
                .set(ENVIRONMENTS.ENABLED, enabled)
                .set(ENVIRONMENTS.UPDATED_AT, OffsetDateTime.now());
        if (effectiveConfigurationChanged) {
            update = update
                    .set(ENVIRONMENTS.CONFIG_VERSION, ENVIRONMENTS.CONFIG_VERSION.plus(1L))
                    .set(ENVIRONMENTS.STATUS, enabled ? EnvironmentStatus.UNKNOWN.name() : EnvironmentStatus.DISABLED.name())
                    .setNull(ENVIRONMENTS.LAST_CONNECTED_AT)
                    .setNull(ENVIRONMENTS.LAST_COLLECTED_AT);
        }
        EnvironmentsRecord record = update
                .where(ENVIRONMENTS.ID.eq(environmentId))
                .returning()
                .fetchOne();
        return record == null ? null : findById(record.getId()).orElseThrow();
    }

    public List<EnvironmentView> findDirectDependents(UUID jumpHostEnvironmentId) {
        return dsl.select(ENVIRONMENTS.fields())
                .from(ENVIRONMENTS)
                .where(JUMP_HOST_ENVIRONMENT_ID.eq(jumpHostEnvironmentId))
                .fetch(this::map);
    }

    public List<EnvironmentView> invalidateConfigurations(Collection<UUID> environmentIds) {
        if (environmentIds == null || environmentIds.isEmpty()) {
            return List.of();
        }
        dsl.update(ENVIRONMENTS)
                .set(ENVIRONMENTS.CONFIG_VERSION, ENVIRONMENTS.CONFIG_VERSION.plus(1L))
                .set(ENVIRONMENTS.STATUS, DSL.when(ENVIRONMENTS.ENABLED, EnvironmentStatus.UNKNOWN.name())
                        .otherwise(EnvironmentStatus.DISABLED.name()))
                .setNull(ENVIRONMENTS.LAST_CONNECTED_AT)
                .setNull(ENVIRONMENTS.LAST_COLLECTED_AT)
                .set(ENVIRONMENTS.UPDATED_AT, OffsetDateTime.now())
                .where(ENVIRONMENTS.ID.in(environmentIds))
                .execute();
        return dsl.select(ENVIRONMENTS.fields())
                .from(ENVIRONMENTS)
                .where(ENVIRONMENTS.ID.in(environmentIds))
                .fetch(this::map);
    }

    public boolean isReferencedAsJumpHost(UUID environmentId) {
        return dsl.fetchExists(ENVIRONMENTS, JUMP_HOST_ENVIRONMENT_ID.eq(environmentId));
    }

    public boolean updateConnectionStatus(UUID environmentId, long configVersion, EnvironmentStatus status, boolean connected) {
        var update = dsl.update(ENVIRONMENTS)
                .set(ENVIRONMENTS.STATUS, status.name())
                .set(ENVIRONMENTS.UPDATED_AT, OffsetDateTime.now());
        if (connected) {
            update = update.set(ENVIRONMENTS.LAST_CONNECTED_AT, OffsetDateTime.now());
        }
        return update.where(ENVIRONMENTS.ID.eq(environmentId)
                        .and(ENVIRONMENTS.CONFIG_VERSION.eq(configVersion)))
                .execute() == 1;
    }

    public boolean updateLastCollectedAt(UUID environmentId, long configVersion) {
        return dsl.update(ENVIRONMENTS)
                .set(ENVIRONMENTS.LAST_COLLECTED_AT, OffsetDateTime.now())
                .set(ENVIRONMENTS.UPDATED_AT, OffsetDateTime.now())
                .where(ENVIRONMENTS.ID.eq(environmentId)
                        .and(ENVIRONMENTS.CONFIG_VERSION.eq(configVersion)))
                .execute() == 1;
    }

    public UUID createSnapshot(
            UUID environmentId,
            UUID projectId,
            UUID taskId,
            String osName,
            String osVersion,
            String kernelVersion,
            String arch,
            String packageManager,
            Map<String, ?> repoSummary,
            Map<String, ?> toolVersions,
            Map<String, ?> rawSnapshot,
            TaskStatus status,
            OffsetDateTime collectedAt,
            long environmentConfigVersion
    ) {
        return dsl.insertInto(ENVIRONMENT_SNAPSHOTS)
                .set(ENVIRONMENT_SNAPSHOTS.ENVIRONMENT_ID, environmentId)
                .set(ENVIRONMENT_SNAPSHOTS.PROJECT_ID, projectId)
                .set(ENVIRONMENT_SNAPSHOTS.TASK_ID, taskId)
                .set(ENVIRONMENT_SNAPSHOTS.ENVIRONMENT_CONFIG_VERSION, environmentConfigVersion)
                .set(ENVIRONMENT_SNAPSHOTS.OS_NAME, osName)
                .set(ENVIRONMENT_SNAPSHOTS.OS_VERSION, osVersion)
                .set(ENVIRONMENT_SNAPSHOTS.KERNEL_VERSION, kernelVersion)
                .set(ENVIRONMENT_SNAPSHOTS.ARCH, arch)
                .set(ENVIRONMENT_SNAPSHOTS.PACKAGE_MANAGER, packageManager)
                .set(ENVIRONMENT_SNAPSHOTS.REPO_SUMMARY, toJsonb(repoSummary))
                .set(ENVIRONMENT_SNAPSHOTS.TOOL_VERSIONS, toJsonb(toolVersions))
                .set(ENVIRONMENT_SNAPSHOTS.RAW_SNAPSHOT, toJsonb(rawSnapshot))
                .set(ENVIRONMENT_SNAPSHOTS.STATUS, status.name())
                .set(ENVIRONMENT_SNAPSHOTS.COLLECTED_AT, collectedAt)
                .returning(ENVIRONMENT_SNAPSHOTS.ID)
                .fetchOne(ENVIRONMENT_SNAPSHOTS.ID);
    }

    public void createComponent(
            UUID snapshotId,
            UUID projectId,
            String name,
            String version,
            String componentType,
            String arch,
            String path,
            String source,
            Map<String, ?> metadata
    ) {
        createComponents(snapshotId, projectId, List.of(new ComponentInput(
                name, version, componentType, arch, path, source, metadata
        )));
    }

    public void createComponents(UUID snapshotId, UUID projectId, List<ComponentInput> components) {
        if (components == null || components.isEmpty()) {
            return;
        }
        for (int offset = 0; offset < components.size(); offset += COMPONENT_BATCH_SIZE) {
            List<ComponentInput> batch = components.subList(offset, Math.min(offset + COMPONENT_BATCH_SIZE, components.size()));
            List<EnvironmentComponentsRecord> records = batch.stream()
                    .map(component -> {
                        EnvironmentComponentsRecord record = dsl.newRecord(ENVIRONMENT_COMPONENTS);
                        record.setSnapshotId(snapshotId);
                        record.setProjectId(projectId);
                        record.setName(component.name());
                        record.setVersion(component.version());
                        record.setComponentType(component.componentType());
                        record.setArch(component.arch());
                        record.setPath(component.path());
                        record.setSource(component.source());
                        record.setMetadata(toJsonb(component.metadata()));
                        return record;
                    })
                    .toList();
            dsl.batchInsert(records).execute();
        }
    }

    public record ComponentInput(
            String name,
            String version,
            String componentType,
            String arch,
            String path,
            String source,
            Map<String, ?> metadata
    ) {
    }

    public EnvironmentSummaryResponse summary(UUID projectId) {
        long total = count(projectId, null, null, null);
        long enabled = count(projectId, null, null, true);
        long source = count(projectId, EnvironmentRole.SOURCE_X86, null, null);
        long target = count(projectId, EnvironmentRole.TARGET_RISCV, null, null);
        long general = count(projectId, EnvironmentRole.GENERAL_EXECUTION, null, null);
        return new EnvironmentSummaryResponse(total, enabled, source, target, general);
    }

    public long countSnapshots(UUID environmentId) {
        return dsl.selectCount()
                .from(ENVIRONMENT_SNAPSHOTS)
                .where(ENVIRONMENT_SNAPSHOTS.ENVIRONMENT_ID.eq(environmentId))
                .fetchOne(0, long.class);
    }

    public List<EnvironmentSnapshotView> listSnapshots(UUID environmentId, int page, int pageSize) {
        return dsl.selectFrom(ENVIRONMENT_SNAPSHOTS)
                .where(ENVIRONMENT_SNAPSHOTS.ENVIRONMENT_ID.eq(environmentId))
                .orderBy(ENVIRONMENT_SNAPSHOTS.COLLECTED_AT.desc(), ENVIRONMENT_SNAPSHOTS.ID.desc())
                .limit(pageSize)
                .offset((page - 1) * pageSize)
                .fetch(EnvironmentSnapshotView::from);
    }

    public Optional<EnvironmentBasicInfoView> findLatestBasicInfo(UUID environmentId, long environmentConfigVersion) {
        return dsl.selectFrom(ENVIRONMENT_SNAPSHOTS)
                .where(ENVIRONMENT_SNAPSHOTS.ENVIRONMENT_ID.eq(environmentId))
                .and(ENVIRONMENT_SNAPSHOTS.ENVIRONMENT_CONFIG_VERSION.eq(environmentConfigVersion))
                .and(ENVIRONMENT_SNAPSHOTS.STATUS.eq(TaskStatus.SUCCEEDED.name()))
                .orderBy(ENVIRONMENT_SNAPSHOTS.COLLECTED_AT.desc(), ENVIRONMENT_SNAPSHOTS.ID.desc())
                .limit(1)
                .fetchOptional(record -> {
                    Map<String, Object> raw = fromJsonb(record.getRawSnapshot());
                    Map<String, Object> checkResults = mapValue(raw.get("checkResults"));
                    return new EnvironmentBasicInfoView(
                            record.getId(),
                            stringValue(raw.getOrDefault("snapshotKind", "FULL_COLLECT")),
                            record.getOsName(),
                            record.getOsVersion(),
                            record.getKernelVersion(),
                            record.getArch(),
                            record.getPackageManager(),
                            firstMap(raw.get("basicTools"), checkResults.get("basicTools")),
                            fromJsonb(record.getToolVersions()),
                            firstMap(raw.get("workingDirectory"), checkResults.get("workingDirectory")),
                            firstMap(raw.get("permissions"), checkResults.get("permissions")),
                            stringValue(raw.get("remoteUser")),
                            record.getCollectedAt()
                    );
                });
    }

    private EnvironmentView map(Record record) {
        return new EnvironmentView(
                record.get(ENVIRONMENTS.ID),
                record.get(ENVIRONMENTS.PROJECT_ID),
                record.get(ENVIRONMENTS.NAME),
                EnvironmentRole.valueOf(record.get(ENVIRONMENTS.ROLE)),
                record.get(ENVIRONMENTS.ARCH),
                record.get(ENVIRONMENTS.HOST),
                record.get(ENVIRONMENTS.SSH_PORT),
                record.get(ENVIRONMENTS.USERNAME),
                record.get(ENVIRONMENTS.CREDENTIAL_ID),
                record.get(JUMP_HOST_ENVIRONMENT_ID),
                record.get(ENVIRONMENTS.WORKING_DIRECTORY),
                EnvironmentStatus.valueOf(record.get(ENVIRONMENTS.STATUS)),
                Boolean.TRUE.equals(record.get(ENVIRONMENTS.ENABLED)),
                record.get(ENVIRONMENTS.CONFIG_VERSION) == null ? 1L : record.get(ENVIRONMENTS.CONFIG_VERSION),
                record.get(ENVIRONMENTS.LAST_CONNECTED_AT),
                record.get(ENVIRONMENTS.LAST_COLLECTED_AT),
                record.get(ENVIRONMENTS.CREATED_BY),
                record.get(ENVIRONMENTS.CREATED_AT),
                record.get(ENVIRONMENTS.UPDATED_AT)
        );
    }

    private Condition filter(UUID projectId, EnvironmentRole role, EnvironmentStatus status, Boolean enabled) {
        Condition condition = ENVIRONMENTS.PROJECT_ID.eq(projectId);
        if (role != null) {
            condition = condition.and(ENVIRONMENTS.ROLE.eq(role.name()));
        }
        if (status != null) {
            condition = condition.and(ENVIRONMENTS.STATUS.eq(status.name()));
        }
        if (enabled != null) {
            condition = condition.and(ENVIRONMENTS.ENABLED.eq(enabled));
        }
        return condition;
    }

    private String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }

    private JSONB toJsonb(Map<String, ?> value) {
        try {
            return JSONB.valueOf(objectMapper.writeValueAsString(value == null ? Map.of() : value));
        } catch (JsonProcessingException ex) {
            return JSONB.valueOf("{}");
        }
    }

    private Map<String, Object> fromJsonb(JSONB value) {
        if (value == null || value.data() == null || value.data().isBlank()) {
            return Map.of();
        }
        try {
            return objectMapper.readValue(value.data(), MAP_TYPE);
        } catch (JsonProcessingException ex) {
            return Map.of();
        }
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> mapValue(Object value) {
        return value instanceof Map<?, ?> map ? (Map<String, Object>) map : Map.of();
    }

    private Map<String, ?> firstMap(Object first, Object second) {
        Map<String, Object> firstMap = mapValue(first);
        return firstMap.isEmpty() ? mapValue(second) : firstMap;
    }

    private String stringValue(Object value) {
        return value == null ? "" : value.toString();
    }
}
