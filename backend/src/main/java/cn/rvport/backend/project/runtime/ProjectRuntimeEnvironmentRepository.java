package cn.rvport.backend.project.runtime;

import static cn.rvport.backend.jooq.tables.ProjectRuntimeEnvironments.PROJECT_RUNTIME_ENVIRONMENTS;

import cn.rvport.backend.jooq.tables.records.ProjectRuntimeEnvironmentsRecord;
import java.time.OffsetDateTime;
import java.util.Collection;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.jooq.DSLContext;
import org.jooq.impl.DSL;
import org.springframework.stereotype.Repository;

@Repository
public class ProjectRuntimeEnvironmentRepository {

    private final DSLContext dsl;

    public ProjectRuntimeEnvironmentRepository(DSLContext dsl) {
        this.dsl = dsl;
    }

    public Optional<ProjectRuntimeEnvironmentView> find(UUID projectId) {
        return dsl.selectFrom(PROJECT_RUNTIME_ENVIRONMENTS)
                .where(PROJECT_RUNTIME_ENVIRONMENTS.PROJECT_ID.eq(projectId))
                .fetchOptional(this::map);
    }

    public ProjectRuntimeEnvironmentView upsert(
            UUID projectId,
            UUID sourceEnvironmentId,
            UUID targetEnvironmentId,
            UUID updatedBy,
            boolean changed
    ) {
        OffsetDateTime now = OffsetDateTime.now();
        ProjectRuntimeEnvironmentsRecord record = dsl.insertInto(PROJECT_RUNTIME_ENVIRONMENTS)
                .set(PROJECT_RUNTIME_ENVIRONMENTS.PROJECT_ID, projectId)
                .set(PROJECT_RUNTIME_ENVIRONMENTS.SOURCE_ENVIRONMENT_ID, sourceEnvironmentId)
                .set(PROJECT_RUNTIME_ENVIRONMENTS.TARGET_ENVIRONMENT_ID, targetEnvironmentId)
                .set(PROJECT_RUNTIME_ENVIRONMENTS.VERSION, 1L)
                .set(PROJECT_RUNTIME_ENVIRONMENTS.UPDATED_BY, updatedBy)
                .set(PROJECT_RUNTIME_ENVIRONMENTS.CREATED_AT, now)
                .set(PROJECT_RUNTIME_ENVIRONMENTS.UPDATED_AT, now)
                .onConflict(PROJECT_RUNTIME_ENVIRONMENTS.PROJECT_ID)
                .doUpdate()
                .set(PROJECT_RUNTIME_ENVIRONMENTS.SOURCE_ENVIRONMENT_ID, sourceEnvironmentId)
                .set(PROJECT_RUNTIME_ENVIRONMENTS.TARGET_ENVIRONMENT_ID, targetEnvironmentId)
                .set(PROJECT_RUNTIME_ENVIRONMENTS.VERSION,
                        changed
                                ? PROJECT_RUNTIME_ENVIRONMENTS.VERSION.plus(1)
                                : PROJECT_RUNTIME_ENVIRONMENTS.VERSION)
                .set(PROJECT_RUNTIME_ENVIRONMENTS.UPDATED_BY, updatedBy)
                .set(PROJECT_RUNTIME_ENVIRONMENTS.UPDATED_AT, now)
                .returning()
                .fetchOne();
        return map(record);
    }

    public long currentVersion(UUID projectId) {
        return find(projectId).map(ProjectRuntimeEnvironmentView::version).orElse(0L);
    }

    public Optional<ProjectRuntimeEnvironmentView> bumpVersionIfSelected(UUID projectId, UUID environmentId, UUID updatedBy) {
        return bumpVersionIfAnySelected(projectId, List.of(environmentId), updatedBy);
    }

    public Optional<ProjectRuntimeEnvironmentView> bumpVersionIfAnySelected(
            UUID projectId,
            Collection<UUID> environmentIds,
            UUID updatedBy
    ) {
        if (environmentIds == null || environmentIds.isEmpty()) {
            return Optional.empty();
        }
        OffsetDateTime now = OffsetDateTime.now();
        Optional<ProjectRuntimeEnvironmentsRecord> record = dsl.update(PROJECT_RUNTIME_ENVIRONMENTS)
                .set(PROJECT_RUNTIME_ENVIRONMENTS.VERSION, PROJECT_RUNTIME_ENVIRONMENTS.VERSION.plus(1))
                .set(PROJECT_RUNTIME_ENVIRONMENTS.UPDATED_BY, updatedBy)
                .set(PROJECT_RUNTIME_ENVIRONMENTS.UPDATED_AT, now)
                .where(PROJECT_RUNTIME_ENVIRONMENTS.PROJECT_ID.eq(projectId)
                        .and(PROJECT_RUNTIME_ENVIRONMENTS.SOURCE_ENVIRONMENT_ID.in(environmentIds)
                                .or(PROJECT_RUNTIME_ENVIRONMENTS.TARGET_ENVIRONMENT_ID.in(environmentIds))))
                .returning()
                .fetchOptional();
        return record.map(this::map);
    }

    public boolean isSelectedEnvironment(UUID environmentId) {
        return dsl.fetchExists(PROJECT_RUNTIME_ENVIRONMENTS,
                PROJECT_RUNTIME_ENVIRONMENTS.SOURCE_ENVIRONMENT_ID.eq(environmentId)
                        .or(PROJECT_RUNTIME_ENVIRONMENTS.TARGET_ENVIRONMENT_ID.eq(environmentId)));
    }

    private ProjectRuntimeEnvironmentView map(ProjectRuntimeEnvironmentsRecord record) {
        if (record == null) {
            return null;
        }
        return new ProjectRuntimeEnvironmentView(
                record.getProjectId(),
                record.getSourceEnvironmentId(),
                record.getTargetEnvironmentId(),
                record.getVersion() == null ? 0L : record.getVersion(),
                record.getUpdatedBy(),
                record.getCreatedAt(),
                record.getUpdatedAt()
        );
    }
}
