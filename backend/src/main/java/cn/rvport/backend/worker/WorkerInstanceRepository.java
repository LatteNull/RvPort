package cn.rvport.backend.worker;

import cn.rvport.backend.common.web.PageResponse;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;
import org.jooq.Condition;
import org.jooq.DSLContext;
import org.jooq.Field;
import org.jooq.JSONB;
import org.jooq.OrderField;
import org.jooq.Record;
import org.jooq.SelectJoinStep;
import org.jooq.Table;
import org.jooq.impl.DSL;
import org.springframework.stereotype.Repository;

@Repository
public class WorkerInstanceRepository {

    private static final Table<?> WORKER_INSTANCES = DSL.table(DSL.name("worker_instances"));

    private final DSLContext dsl;

    public WorkerInstanceRepository(DSLContext dsl) {
        this.dsl = dsl;
    }

    public WorkerInstanceView upsertHeartbeat(
            String instanceId,
            String hostname,
            long processId,
            String appVersion,
            int defaultConcurrencyLimit,
            int activeConcurrency,
            int activeTaskCount
    ) {
        OffsetDateTime now = OffsetDateTime.now();
        Record record = dsl.insertInto(WORKER_INSTANCES)
                .columns(
                        field("instance_id", String.class),
                        field("hostname", String.class),
                        field("process_id", Long.class),
                        field("app_version", String.class),
                        field("status", String.class),
                        field("concurrency_limit", Integer.class),
                        field("active_concurrency", Integer.class),
                        field("active_task_count", Integer.class),
                        field("started_at", OffsetDateTime.class),
                        field("last_heartbeat_at", OffsetDateTime.class),
                        field("metadata", JSONB.class),
                        field("updated_at", OffsetDateTime.class)
                )
                .values(
                        instanceId,
                        hostname,
                        processId,
                        appVersion,
                        WorkerInstanceStatus.ONLINE.name(),
                        defaultConcurrencyLimit,
                        activeConcurrency,
                        activeTaskCount,
                        now,
                        now,
                        JSONB.valueOf("{}"),
                        now
                )
                .onConflict(field("instance_id", String.class))
                .doUpdate()
                .set(field("hostname", String.class), hostname)
                .set(field("process_id", Long.class), processId)
                .set(field("app_version", String.class), appVersion)
                .set(field("status", String.class), WorkerInstanceStatus.ONLINE.name())
                .set(field("active_concurrency", Integer.class), activeConcurrency)
                .set(field("active_task_count", Integer.class), activeTaskCount)
                .set(field("last_heartbeat_at", OffsetDateTime.class), now)
                .set(field("updated_at", OffsetDateTime.class), now)
                .returning()
                .fetchOne();
        return from(record, now);
    }

    public PageResponse<WorkerInstanceView> list(WorkerInstanceListRequest request, int offlineTimeoutSeconds) {
        OffsetDateTime onlineSince = OffsetDateTime.now().minusSeconds(offlineTimeoutSeconds);
        Condition condition = condition(request, onlineSince);
        int page = request.normalizedPage();
        int pageSize = request.normalizedPageSize();
        long total = dsl.selectCount()
                .from(WORKER_INSTANCES)
                .where(condition)
                .fetchOne(0, long.class);
        List<WorkerInstanceView> items = baseSelect()
                .where(condition)
                .orderBy(sort(request))
                .limit(pageSize)
                .offset((page - 1) * pageSize)
                .fetch(record -> from(record, onlineSince));
        return PageResponse.of(items, page, pageSize, total);
    }

    public Optional<WorkerInstanceView> findByInstanceId(String instanceId, int offlineTimeoutSeconds) {
        OffsetDateTime onlineSince = OffsetDateTime.now().minusSeconds(offlineTimeoutSeconds);
        return baseSelect()
                .where(field("instance_id", String.class).eq(instanceId))
                .fetchOptional()
                .map(record -> from(record, onlineSince));
    }

    public Optional<Integer> findConcurrencyLimit(String instanceId) {
        return dsl.select(field("concurrency_limit", Integer.class))
                .from(WORKER_INSTANCES)
                .where(field("instance_id", String.class).eq(instanceId))
                .fetchOptional(field("concurrency_limit", Integer.class));
    }

    public WorkerInstanceView updateConcurrencyLimit(String instanceId, int concurrencyLimit, int offlineTimeoutSeconds) {
        OffsetDateTime now = OffsetDateTime.now();
        dsl.update(WORKER_INSTANCES)
                .set(field("concurrency_limit", Integer.class), concurrencyLimit)
                .set(field("updated_at", OffsetDateTime.class), now)
                .where(field("instance_id", String.class).eq(instanceId))
                .execute();
        return findByInstanceId(instanceId, offlineTimeoutSeconds).orElse(null);
    }

    public int markOfflineBefore(OffsetDateTime cutoff, int limit) {
        List<String> instanceIds = dsl.select(field("instance_id", String.class))
                .from(WORKER_INSTANCES)
                .where(field("last_heartbeat_at", OffsetDateTime.class).lt(cutoff)
                        .and(field("status", String.class).ne(WorkerInstanceStatus.OFFLINE.name())))
                .orderBy(field("last_heartbeat_at", OffsetDateTime.class).asc())
                .limit(limit)
                .fetch(field("instance_id", String.class));
        if (instanceIds.isEmpty()) {
            return 0;
        }
        return dsl.update(WORKER_INSTANCES)
                .set(field("status", String.class), WorkerInstanceStatus.OFFLINE.name())
                .set(field("updated_at", OffsetDateTime.class), OffsetDateTime.now())
                .where(field("instance_id", String.class).in(instanceIds)
                        .and(field("last_heartbeat_at", OffsetDateTime.class).lt(cutoff)))
                .execute();
    }

    public List<String> findInstanceIdsBefore(OffsetDateTime cutoff, int limit) {
        return dsl.select(field("instance_id", String.class))
                .from(WORKER_INSTANCES)
                .where(field("last_heartbeat_at", OffsetDateTime.class).lt(cutoff))
                .orderBy(field("last_heartbeat_at", OffsetDateTime.class).asc())
                .limit(limit)
                .fetch(field("instance_id", String.class));
    }

    public boolean lockIfStillStale(String instanceId, OffsetDateTime cutoff) {
        return dsl.select(field("instance_id", String.class))
                .from(WORKER_INSTANCES)
                .where(field("instance_id", String.class).eq(instanceId)
                        .and(field("last_heartbeat_at", OffsetDateTime.class).lt(cutoff)))
                .forUpdate()
                .skipLocked()
                .fetchOptional()
                .isPresent();
    }

    public boolean lockForClaim(String instanceId) {
        return dsl.select(field("instance_id", String.class)).from(WORKER_INSTANCES)
                .where(field("instance_id", String.class).eq(instanceId))
                .forUpdate().fetchOptional().isPresent();
    }

    public int deleteIfRetired(String instanceId, OffsetDateTime cutoff) {
        Table<?> handles = DSL.table(DSL.name("task_runtime_handles")).as("h");
        Field<String> workerId = DSL.field(DSL.name("worker_instances", "instance_id"), String.class);
        Field<OffsetDateTime> heartbeat = DSL.field(
                DSL.name("worker_instances", "last_heartbeat_at"),
                OffsetDateTime.class
        );
        return dsl.deleteFrom(WORKER_INSTANCES)
                .where(workerId.eq(instanceId)
                        .and(heartbeat.lt(cutoff))
                        .andNotExists(dsl.selectOne()
                                .from(handles)
                                .where(DSL.field(DSL.name("h", "worker_instance_id"), String.class).eq(workerId)
                                        .and(DSL.field(DSL.name("h", "status"), String.class).in(
                                                "ACTIVE",
                                                "CANCEL_REQUESTED",
                                                "CANCELLING"
                                        )))))
                .execute();
    }

    private SelectJoinStep<? extends Record> baseSelect() {
        return dsl.select(
                        field("instance_id", String.class),
                        field("hostname", String.class),
                        field("process_id", Long.class),
                        field("app_version", String.class),
                        field("status", String.class),
                        field("concurrency_limit", Integer.class),
                        field("active_concurrency", Integer.class),
                        field("active_task_count", Integer.class),
                        field("started_at", OffsetDateTime.class),
                        field("last_heartbeat_at", OffsetDateTime.class),
                        field("created_at", OffsetDateTime.class),
                        field("updated_at", OffsetDateTime.class)
                )
                .from(WORKER_INSTANCES);
    }

    private Condition condition(WorkerInstanceListRequest request, OffsetDateTime onlineSince) {
        Condition condition = DSL.trueCondition();
        if (request.status() == WorkerInstanceStatus.ONLINE) {
            condition = condition.and(field("last_heartbeat_at", OffsetDateTime.class).ge(onlineSince));
        } else if (request.status() == WorkerInstanceStatus.OFFLINE) {
            condition = condition.and(field("last_heartbeat_at", OffsetDateTime.class).lt(onlineSince));
        }
        if (notBlank(request.instanceId())) {
            condition = condition.and(field("instance_id", String.class).containsIgnoreCase(request.instanceId().trim()));
        }
        if (notBlank(request.hostname())) {
            condition = condition.and(field("hostname", String.class).containsIgnoreCase(request.hostname().trim()));
        }
        if (Boolean.TRUE.equals(request.hasRunningTasks())) {
            condition = condition.and(field("active_task_count", Integer.class).gt(0));
        } else if (Boolean.FALSE.equals(request.hasRunningTasks())) {
            condition = condition.and(field("active_task_count", Integer.class).eq(0));
        }
        return condition;
    }

    private OrderField<?> sort(WorkerInstanceListRequest request) {
        Field<?> sortField = switch (blankToDefault(request.sortBy(), "lastHeartbeatAt")) {
            case "instanceId" -> field("instance_id", String.class);
            case "hostname" -> field("hostname", String.class);
            case "status" -> field("status", String.class);
            case "concurrencyLimit" -> field("concurrency_limit", Integer.class);
            case "activeConcurrency" -> field("active_concurrency", Integer.class);
            case "activeTaskCount" -> field("active_task_count", Integer.class);
            case "startedAt" -> field("started_at", OffsetDateTime.class);
            case "updatedAt" -> field("updated_at", OffsetDateTime.class);
            case "lastHeartbeatAt" -> field("last_heartbeat_at", OffsetDateTime.class);
            default -> throw new IllegalArgumentException("Unsupported worker sort field: " + request.sortBy());
        };
        return "asc".equalsIgnoreCase(request.sortDirection()) ? sortField.asc().nullsLast() : sortField.desc().nullsLast();
    }

    private static WorkerInstanceView from(Record record, OffsetDateTime onlineSince) {
        if (record == null) {
            return null;
        }
        OffsetDateTime lastHeartbeatAt = record.get(field("last_heartbeat_at", OffsetDateTime.class));
        WorkerInstanceStatus status = lastHeartbeatAt != null && !lastHeartbeatAt.isBefore(onlineSince)
                ? WorkerInstanceStatus.ONLINE
                : WorkerInstanceStatus.OFFLINE;
        return new WorkerInstanceView(
                record.get(field("instance_id", String.class)),
                record.get(field("hostname", String.class)),
                record.get(field("process_id", Long.class)),
                record.get(field("app_version", String.class)),
                status,
                defaultInt(record.get(field("concurrency_limit", Integer.class))),
                defaultInt(record.get(field("active_concurrency", Integer.class))),
                defaultInt(record.get(field("active_task_count", Integer.class))),
                record.get(field("started_at", OffsetDateTime.class)),
                lastHeartbeatAt,
                record.get(field("created_at", OffsetDateTime.class)),
                record.get(field("updated_at", OffsetDateTime.class))
        );
    }

    private static boolean notBlank(String value) {
        return value != null && !value.isBlank();
    }

    private static String blankToDefault(String value, String defaultValue) {
        return value == null || value.isBlank() ? defaultValue : value.trim();
    }

    private static int defaultInt(Integer value) {
        return value == null ? 0 : value;
    }

    private static <T> Field<T> field(String name, Class<T> type) {
        return DSL.field(DSL.name(name), type);
    }
}
