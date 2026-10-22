package cn.rvport.backend.task;

import static cn.rvport.backend.jooq.tables.Environments.ENVIRONMENTS;
import static cn.rvport.backend.jooq.tables.TaskLogEvents.TASK_LOG_EVENTS;
import static cn.rvport.backend.jooq.tables.Tasks.TASKS;
import static cn.rvport.backend.jooq.tables.ToolRuns.TOOL_RUNS;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.jooq.Condition;
import org.jooq.DSLContext;
import org.jooq.Field;
import org.jooq.JSONB;
import org.jooq.Record;
import org.jooq.SortField;
import org.jooq.impl.DSL;
import org.springframework.stereotype.Repository;

@Repository
public class ScriptExecutionRepository {

    private static final Field<UUID> INPUT_ENVIRONMENT_ID = DSL.field("({0}->>'environmentId')::uuid", UUID.class, TASKS.INPUT_SNAPSHOT);
    private static final Field<UUID> INPUT_PAYLOAD_ID = DSL.field("({0}->>'scriptPayloadId')::uuid", UUID.class, TASKS.INPUT_SNAPSHOT);
    private static final Field<String> INPUT_SCRIPT_TYPE = DSL.field("{0}->>'scriptType'", String.class, TASKS.INPUT_SNAPSHOT);
    private static final Field<String> INPUT_SCRIPT_SHA256 = DSL.field("{0}->>'scriptSha256'", String.class, TASKS.INPUT_SNAPSHOT);
    private static final Field<Integer> INPUT_SCRIPT_LENGTH = DSL.field("({0}->>'scriptLength')::int", Integer.class, TASKS.INPUT_SNAPSHOT);
    private static final Field<Integer> LOG_EVENT_COUNT = DSL.selectCount()
            .from(TASK_LOG_EVENTS)
            .where(TASK_LOG_EVENTS.TASK_ID.eq(TASKS.ID))
            .asField("log_event_count");

    private final DSLContext dsl;

    public ScriptExecutionRepository(DSLContext dsl) {
        this.dsl = dsl;
    }

    public long count(UUID projectId, ScriptExecutionListRequest request) {
        return dsl.selectCount()
                .from(TASKS)
                .leftJoin(ENVIRONMENTS).on(ENVIRONMENTS.ID.eq(INPUT_ENVIRONMENT_ID))
                .where(filter(projectId, request))
                .fetchOne(0, long.class);
    }

    public List<Row> list(UUID projectId, ScriptExecutionListRequest request) {
        return dsl.select(
                        TASKS.ID,
                        TASKS.PROJECT_ID,
                        INPUT_ENVIRONMENT_ID.as("environment_id"),
                        ENVIRONMENTS.NAME.as("environment_name"),
                        TASKS.STATUS,
                        TASKS.PROGRESS,
                        TASKS.MESSAGE,
                        INPUT_SCRIPT_SHA256.as("script_sha256"),
                        INPUT_SCRIPT_LENGTH.as("script_length"),
                        latestToolRunExitCode().as("exit_code"),
                        LOG_EVENT_COUNT,
                        TASKS.CREATED_AT,
                        TASKS.STARTED_AT,
                        TASKS.FINISHED_AT
                )
                .from(TASKS)
                .leftJoin(ENVIRONMENTS).on(ENVIRONMENTS.ID.eq(INPUT_ENVIRONMENT_ID))
                .where(filter(projectId, request))
                .orderBy(sort(request.normalizedSort()))
                .limit(request.normalizedPageSize())
                .offset((request.normalizedPage() - 1) * request.normalizedPageSize())
                .fetch(this::mapRow);
    }

    public Optional<DetailRow> findDetail(UUID taskId) {
        return dsl.select(
                        TASKS.ID,
                        TASKS.PROJECT_ID,
                        INPUT_ENVIRONMENT_ID.as("environment_id"),
                        ENVIRONMENTS.NAME.as("environment_name"),
                        TASKS.STATUS,
                        TASKS.PROGRESS,
                        TASKS.MESSAGE,
                        INPUT_SCRIPT_SHA256.as("script_sha256"),
                        INPUT_SCRIPT_LENGTH.as("script_length"),
                        TOOL_RUNS.ID.as("tool_run_id"),
                        TOOL_RUNS.TOOL_NAME,
                        TOOL_RUNS.EXIT_CODE,
                        TOOL_RUNS.SUMMARY,
                        LOG_EVENT_COUNT,
                        TASKS.CREATED_AT,
                        TASKS.STARTED_AT,
                        TASKS.FINISHED_AT
                )
                .from(TASKS)
                .leftJoin(ENVIRONMENTS).on(ENVIRONMENTS.ID.eq(INPUT_ENVIRONMENT_ID))
                .leftJoin(TOOL_RUNS).on(TOOL_RUNS.ID.eq(latestToolRunId()))
                .where(baseFilter(null).and(TASKS.ID.eq(taskId)))
                .fetchOptional(this::mapDetail);
    }

    private Field<UUID> latestToolRunId() {
        return DSL.select(TOOL_RUNS.ID)
                .from(TOOL_RUNS)
                .where(TOOL_RUNS.TASK_ID.eq(TASKS.ID))
                .orderBy(TOOL_RUNS.STARTED_AT.desc().nullsLast(), TOOL_RUNS.ID.desc())
                .limit(1)
                .asField();
    }

    private Field<Integer> latestToolRunExitCode() {
        return DSL.select(TOOL_RUNS.EXIT_CODE)
                .from(TOOL_RUNS)
                .where(TOOL_RUNS.TASK_ID.eq(TASKS.ID))
                .orderBy(TOOL_RUNS.STARTED_AT.desc().nullsLast(), TOOL_RUNS.ID.desc())
                .limit(1)
                .asField();
    }

    private Condition filter(UUID projectId, ScriptExecutionListRequest request) {
        Condition condition = baseFilter(projectId);
        if (request.status() != null) {
            condition = switch (request.status()) {
                case RUNNING -> condition.and(TASKS.STATUS.in(
                        TaskStatus.PENDING.name(), TaskStatus.QUEUED.name(), TaskStatus.RUNNING.name()));
                case SUCCEEDED -> condition.and(TASKS.STATUS.eq(TaskStatus.SUCCEEDED.name()));
                case ERROR -> condition.and(TASKS.STATUS.in(
                        TaskStatus.FAILED.name(), TaskStatus.TIMEOUT.name(), TaskStatus.CANCELLED.name()));
            };
        }
        if (request.environmentId() != null) {
            condition = condition.and(INPUT_ENVIRONMENT_ID.eq(request.environmentId()));
        }
        if (request.keyword() != null && !request.keyword().isBlank()) {
            String keyword = "%" + request.keyword().trim().toLowerCase() + "%";
            condition = condition.and(DSL.lower(ENVIRONMENTS.NAME).like(keyword)
                    .or(DSL.lower(TASKS.MESSAGE).like(keyword)));
        }
        return condition;
    }

    private Condition baseFilter(UUID projectId) {
        Condition condition = TASKS.TYPE.eq(RvPortTaskTypes.ENV_RUN_SCRIPT)
                .and(INPUT_SCRIPT_TYPE.eq("CUSTOM_BASH"))
                .and(INPUT_PAYLOAD_ID.isNotNull());
        if (projectId != null) {
            condition = condition.and(TASKS.PROJECT_ID.eq(projectId));
        }
        return condition;
    }

    private SortField<?> sort(String sort) {
        return switch (sort) {
            case "createdAt.asc" -> TASKS.CREATED_AT.asc();
            case "status.asc" -> TASKS.STATUS.asc();
            case "status.desc" -> TASKS.STATUS.desc();
            case "environmentName.asc" -> ENVIRONMENTS.NAME.asc().nullsLast();
            case "environmentName.desc" -> ENVIRONMENTS.NAME.desc().nullsLast();
            default -> TASKS.CREATED_AT.desc();
        };
    }

    private Row mapRow(Record record) {
        return new Row(
                record.get(TASKS.ID),
                record.get(TASKS.PROJECT_ID),
                record.get("environment_id", UUID.class),
                record.get("environment_name", String.class),
                TaskStatus.valueOf(record.get(TASKS.STATUS)),
                record.get(TASKS.PROGRESS),
                record.get(TASKS.MESSAGE),
                record.get("script_sha256", String.class),
                record.get("script_length", Integer.class),
                record.get("exit_code", Integer.class),
                record.get("log_event_count", Integer.class) == null ? 0L : record.get("log_event_count", Integer.class).longValue(),
                record.get(TASKS.CREATED_AT),
                record.get(TASKS.STARTED_AT),
                record.get(TASKS.FINISHED_AT)
        );
    }

    private DetailRow mapDetail(Record record) {
        Row base = mapRow(record);
        return new DetailRow(
                base,
                record.get("tool_run_id", UUID.class),
                record.get(TOOL_RUNS.TOOL_NAME),
                record.get(TOOL_RUNS.SUMMARY)
        );
    }

    public record Row(
            UUID taskId,
            UUID projectId,
            UUID environmentId,
            String environmentName,
            TaskStatus taskStatus,
            Integer progress,
            String message,
            String scriptSha256,
            Integer scriptLength,
            Integer exitCode,
            long logEventCount,
            OffsetDateTime createdAt,
            OffsetDateTime startedAt,
            OffsetDateTime finishedAt
    ) {
    }

    public record DetailRow(
            Row row,
            UUID toolRunId,
            String toolName,
            JSONB summary
    ) {
    }
}
