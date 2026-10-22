package cn.rvport.backend.task;

import static cn.rvport.backend.jooq.tables.Tasks.TASKS;
import static cn.rvport.backend.workflow.DomainLatestOrdering.activeFirst;

import cn.rvport.backend.jooq.tables.records.TasksRecord;
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
import org.jooq.impl.DSL;
import org.springframework.stereotype.Repository;

@Repository
public class TaskRepository {

    private final DSLContext dsl;

    public TaskRepository(DSLContext dsl) {
        this.dsl = dsl;
    }

    public TaskView create(TaskCreateCommand command, String inputSnapshotJson) {
        TasksRecord record = dsl.insertInto(TASKS)
                .set(TASKS.PROJECT_ID, command.projectId())
                .set(TASKS.TYPE, command.type())
                .set(TASKS.STATUS, TaskStatus.PENDING.name())
                .set(TASKS.PROGRESS, 0)
                .set(TASKS.MESSAGE, command.message())
                .set(TASKS.INPUT_SNAPSHOT, JSONB.valueOf(inputSnapshotJson))
                .set(TASKS.CREATED_BY, command.createdBy())
                .set(TASKS.TIMEOUT_SECONDS, command.timeoutSeconds())
                .set(TASKS.STAGE_ID, blankToNull(command.stageId()))
                .set(TASKS.RESOURCE_TYPE, blankToNull(command.resourceType()))
                .set(TASKS.RESOURCE_ID, command.resourceId())
                .set(TASKS.RESOURCE_MODE, blankToNull(command.resourceMode()))
                .set(TASKS.ENVIRONMENT_ROLE, blankToNull(command.environmentRole()))
                .returning()
                .fetchOne();
        return TaskView.from(record);
    }

    public Optional<TaskView> findById(UUID taskId) {
        return dsl.selectFrom(TASKS)
                .where(TASKS.ID.eq(taskId))
                .fetchOptional()
                .map(TaskView::from);
    }

    public Optional<TasksRecord> findRecordById(UUID taskId) {
        return dsl.selectFrom(TASKS)
                .where(TASKS.ID.eq(taskId))
                .fetchOptional();
    }

    public long count(UUID projectId, TaskStatus status, String type) {
        return dsl.selectCount()
                .from(TASKS)
                .where(filter(projectId, status, type))
                .fetchOne(0, long.class);
    }

    public List<TaskView> list(UUID projectId, TaskStatus status, String type, int page, int pageSize) {
        return dsl.selectFrom(TASKS)
                .where(filter(projectId, status, type))
                .orderBy(TASKS.CREATED_AT.desc(), TASKS.ID.desc())
                .limit(pageSize)
                .offset((page - 1) * pageSize)
                .fetch(TaskView::from);
    }

    public Optional<TaskView> findLatestByStage(UUID projectId, String stageId) {
        return dsl.selectFrom(TASKS)
                .where(TASKS.PROJECT_ID.eq(projectId)
                        .and(TASKS.STAGE_ID.eq(stageId)))
                .orderBy(activeFirst(TASKS.STATUS), TASKS.CREATED_AT.desc(), TASKS.ID.desc())
                .limit(1)
                .fetchOptional()
                .map(TaskView::from);
    }

    public Map<UUID, TaskView> findByIds(Collection<UUID> taskIds) {
        if (taskIds == null || taskIds.isEmpty()) {
            return Map.of();
        }
        return dsl.selectFrom(TASKS)
                .where(TASKS.ID.in(taskIds))
                .fetch(TaskView::from)
                .stream()
                .collect(java.util.stream.Collectors.toMap(TaskView::id, task -> task));
    }

    public Optional<TaskView> findLatestByStageAndResources(
            UUID projectId,
            String stageId,
            Collection<UUID> resourceIds
    ) {
        if (resourceIds == null || resourceIds.isEmpty()) {
            return Optional.empty();
        }
        return dsl.selectFrom(TASKS)
                .where(TASKS.PROJECT_ID.eq(projectId)
                        .and(TASKS.STAGE_ID.eq(stageId))
                        .and(TASKS.RESOURCE_ID.in(resourceIds)))
                .orderBy(activeFirst(TASKS.STATUS), TASKS.CREATED_AT.desc(), TASKS.ID.desc())
                .limit(1)
                .fetchOptional()
                .map(TaskView::from);
    }

    public Optional<TaskView> findLatestByStageAndResourceVersions(
            UUID projectId,
            String stageId,
            Map<UUID, Long> resourceVersions
    ) {
        if (resourceVersions == null || resourceVersions.isEmpty()) {
            return Optional.empty();
        }
        Field<String> configVersion = DSL.field(
                "({0} ->> 'environmentConfigVersion')",
                String.class,
                TASKS.INPUT_SNAPSHOT
        );
        Condition matchingResourceVersion = DSL.falseCondition();
        for (Map.Entry<UUID, Long> entry : resourceVersions.entrySet()) {
            matchingResourceVersion = matchingResourceVersion.or(
                    TASKS.RESOURCE_ID.eq(entry.getKey())
                            .and(configVersion.eq(Long.toString(entry.getValue())))
            );
        }
        return dsl.selectFrom(TASKS)
                .where(TASKS.PROJECT_ID.eq(projectId)
                        .and(TASKS.STAGE_ID.eq(stageId))
                        .and(matchingResourceVersion))
                .orderBy(activeFirst(TASKS.STATUS), TASKS.CREATED_AT.desc(), TASKS.ID.desc())
                .limit(1)
                .fetchOptional()
                .map(TaskView::from);
    }

    public TaskView markQueued(UUID taskId) {
        TasksRecord record = dsl.update(TASKS)
                .set(TASKS.STATUS, TaskStatus.QUEUED.name())
                .set(TASKS.QUEUED_AT, OffsetDateTime.now())
                .where(TASKS.ID.eq(taskId)
                        .and(TASKS.STATUS.eq(TaskStatus.PENDING.name())))
                .returning()
                .fetchOne();
        return record == null ? null : TaskView.from(record);
    }

    public TaskView claim(UUID taskId, String message) {
        TasksRecord record = dsl.update(TASKS)
                .set(TASKS.STATUS, TaskStatus.RUNNING.name())
                .set(TASKS.STARTED_AT, OffsetDateTime.now())
                .set(TASKS.PROGRESS, DSL.coalesce(TASKS.PROGRESS, 0))
                .set(TASKS.MESSAGE, message)
                .where(TASKS.ID.eq(taskId)
                        .and(TASKS.STATUS.in(TaskStatus.PENDING.name(), TaskStatus.QUEUED.name())))
                .returning()
                .fetchOne();
        return record == null ? null : TaskView.from(record);
    }

    public TaskView updateProgress(UUID taskId, int progress, String message) {
        TasksRecord record = dsl.update(TASKS)
                .set(TASKS.PROGRESS, progress)
                .set(TASKS.MESSAGE, message)
                .where(TASKS.ID.eq(taskId).and(TASKS.STATUS.eq(TaskStatus.RUNNING.name())))
                .returning()
                .fetchOne();
        return record == null ? null : TaskView.from(record);
    }

    public TaskView markRetry(UUID taskId, int retryCount, String message, String errorCode, String errorMessage) {
        TasksRecord record = dsl.update(TASKS)
                .set(TASKS.STATUS, TaskStatus.QUEUED.name())
                .set(TASKS.RETRY_COUNT, retryCount)
                .set(TASKS.MESSAGE, message)
                .set(TASKS.ERROR_CODE, errorCode)
                .set(TASKS.ERROR_MESSAGE, errorMessage)
                .set(TASKS.QUEUED_AT, OffsetDateTime.now())
                .where(TASKS.ID.eq(taskId).and(TASKS.STATUS.eq(TaskStatus.RUNNING.name())))
                .returning()
                .fetchOne();
        return record == null ? null : TaskView.from(record);
    }

    public TaskView complete(UUID taskId, TaskStatus status, String message, String errorCode, String errorMessage) {
        TaskView changed = completeIfActive(taskId, status, message, errorCode, errorMessage);
        return changed == null ? findById(taskId).orElse(null) : changed;
    }

    public TaskView completeIfActive(UUID taskId, TaskStatus status, String message, String errorCode, String errorMessage) {
        var update = dsl.update(TASKS)
                .set(TASKS.STATUS, status.name())
                .set(TASKS.MESSAGE, message)
                .set(TASKS.ERROR_CODE, errorCode)
                .set(TASKS.ERROR_MESSAGE, errorMessage)
                .set(TASKS.FINISHED_AT, OffsetDateTime.now());
        if (status == TaskStatus.SUCCEEDED) {
            update = update.set(TASKS.PROGRESS, 100);
        }
        TasksRecord record = update.where(TASKS.ID.eq(taskId)
                        .and(TASKS.STATUS.in(TaskStatus.PENDING.name(), TaskStatus.QUEUED.name(), TaskStatus.RUNNING.name())))
                .returning()
                .fetchOne();
        return record == null ? null : TaskView.from(record);
    }

    public TaskView lockById(UUID taskId) {
        TasksRecord record = dsl.selectFrom(TASKS).where(TASKS.ID.eq(taskId)).forUpdate().fetchOne();
        return record == null ? null : TaskView.from(record);
    }

    public TaskView failRunningWorkerLost(UUID taskId, String message) {
        TasksRecord record = dsl.update(TASKS)
                .set(TASKS.STATUS, TaskStatus.FAILED.name())
                .set(TASKS.MESSAGE, message)
                .set(TASKS.ERROR_CODE, TaskErrorCode.WORKER_LOST)
                .set(TASKS.ERROR_MESSAGE, message)
                .set(TASKS.FINISHED_AT, OffsetDateTime.now())
                .where(TASKS.ID.eq(taskId)
                        .and(TASKS.STATUS.eq(TaskStatus.RUNNING.name())))
                .returning()
                .fetchOne();
        return record == null ? null : TaskView.from(record);
    }

    public TaskView cancelPendingOrQueued(UUID taskId, UUID actorUserId, String reason) {
        TasksRecord record = dsl.update(TASKS)
                .set(TASKS.STATUS, TaskStatus.CANCELLED.name())
                .set(TASKS.MESSAGE, "任务已取消")
                .set(TASKS.FINISHED_AT, OffsetDateTime.now())
                .set(field("cancel_requested_at", OffsetDateTime.class), OffsetDateTime.now())
                .set(field("cancel_requested_by", UUID.class), actorUserId)
                .set(field("cancel_reason", String.class), reason)
                .where(TASKS.ID.eq(taskId)
                        .and(TASKS.STATUS.in(TaskStatus.PENDING.name(), TaskStatus.QUEUED.name())))
                .returning()
                .fetchOne();
        return record == null ? null : TaskView.from(record);
    }

    public TaskView cancelPendingOrQueued(UUID taskId) {
        return cancelPendingOrQueued(taskId, null, null);
    }

    public TaskView cancelRunning(UUID taskId, UUID actorUserId, String reason) {
        TasksRecord record = dsl.update(TASKS)
                .set(TASKS.STATUS, TaskStatus.CANCELLED.name())
                .set(TASKS.MESSAGE, "任务已取消，正在清理运行资源")
                .set(TASKS.FINISHED_AT, OffsetDateTime.now())
                .set(field("cancel_requested_at", OffsetDateTime.class), OffsetDateTime.now())
                .set(field("cancel_requested_by", UUID.class), actorUserId)
                .set(field("cancel_reason", String.class), reason)
                .where(TASKS.ID.eq(taskId)
                        .and(TASKS.STATUS.eq(TaskStatus.RUNNING.name())))
                .returning()
                .fetchOne();
        return record == null ? null : TaskView.from(record);
    }

    public List<TaskView> findPendingBefore(OffsetDateTime before, int limit) {
        return dsl.selectFrom(TASKS)
                .where(TASKS.STATUS.eq(TaskStatus.PENDING.name())
                        .and(TASKS.CREATED_AT.lt(before)))
                .orderBy(TASKS.CREATED_AT.asc())
                .limit(limit)
                .fetch(TaskView::from);
    }

    public boolean isTerminal(TaskStatus status) {
        return terminalStatuses().contains(status);
    }

    private Collection<TaskStatus> terminalStatuses() {
        return List.of(TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.TIMEOUT);
    }

    private Condition filter(UUID projectId, TaskStatus status, String type) {
        Condition condition = TASKS.PROJECT_ID.eq(projectId);
        if (status != null) {
            condition = condition.and(TASKS.STATUS.eq(status.name()));
        }
        if (type != null && !type.isBlank()) {
            condition = condition.and(TASKS.TYPE.eq(type.trim()));
        }
        return condition;
    }

    private static <T> Field<T> field(String name, Class<T> type) {
        return DSL.field(DSL.name(name), type);
    }

    private String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }
}
