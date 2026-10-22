package cn.rvport.backend.automatedtest;

import static cn.rvport.backend.jooq.tables.Environments.ENVIRONMENTS;
import static cn.rvport.backend.jooq.tables.BuildRuns.BUILD_RUNS;
import static cn.rvport.backend.jooq.tables.Tasks.TASKS;
import static cn.rvport.backend.jooq.tables.TestRuns.TEST_RUNS;
import static cn.rvport.backend.workflow.DomainLatestOrdering.activeFirst;

import cn.rvport.backend.jooq.tables.records.TestRunsRecord;
import cn.rvport.backend.task.TaskStatus;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.jooq.Condition;
import org.jooq.DSLContext;
import org.jooq.Field;
import org.jooq.JSONB;
import org.jooq.OrderField;
import org.jooq.Record;
import org.jooq.impl.DSL;
import org.springframework.stereotype.Repository;

@Repository
public class AutomatedTestRepository {

    private static final TypeReference<List<Map<String, Object>>> REPORT_ARTIFACTS_TYPE = new TypeReference<>() {
    };
    private static final Field<String> OUTPUT_SUMMARY = DSL.field(DSL.name("test_runs", "output_summary"), String.class);
    private static final Field<JSONB> REPORT_ARTIFACTS = DSL.field(DSL.name("test_runs", "report_artifacts"), JSONB.class);

    private final DSLContext dsl;
    private final ObjectMapper objectMapper;

    public AutomatedTestRepository(DSLContext dsl, ObjectMapper objectMapper) {
        this.dsl = dsl;
        this.objectMapper = objectMapper;
    }

    public UUID createPending(AutomatedTestInput input, UUID taskId) {
        return dsl.insertInto(TEST_RUNS)
                .set(TEST_RUNS.PROJECT_ID, input.projectId())
                .set(TEST_RUNS.TASK_ID, taskId)
                .set(TEST_RUNS.BUILD_RUN_ID, input.buildRunId())
                .set(TEST_RUNS.SOURCE_REVISION_ID, input.sourceRevisionId())
                .set(TEST_RUNS.ENVIRONMENT_ID, input.environmentId())
                .set(TEST_RUNS.ENVIRONMENT_CONFIG_VERSION, input.environmentConfigVersion())
                .set(TEST_RUNS.TEST_BATCH_ID, input.testBatchId())
                .set(TEST_RUNS.TEST_BATCH_ROLE, input.testBatchRole() == null ? null : input.testBatchRole().name())
                .set(TEST_RUNS.COMMAND, input.command())
                .set(TEST_RUNS.WORKING_DIRECTORY, blankToNull(input.workingDirectory()))
                .set(TEST_RUNS.TIMEOUT_SECONDS, input.timeoutSeconds())
                .set(TEST_RUNS.STATUS, TaskStatus.PENDING.name())
                .returning(TEST_RUNS.ID)
                .fetchOne(TEST_RUNS.ID);
    }

    public Optional<AutomatedTestRunView> findById(UUID id) {
        return baseSelect().where(TEST_RUNS.ID.eq(id)).fetchOptional(this::map);
    }

    public Optional<AutomatedTestRunView> findByTaskId(UUID taskId) {
        return baseSelect().where(TEST_RUNS.TASK_ID.eq(taskId)).fetchOptional(this::map);
    }

    public Optional<AutomatedTestRunView> findBatchPeer(AutomatedTestRunView run, TestBatchRole peerRole) {
        if (run == null || run.testBatchId() == null || peerRole == null) {
            return Optional.empty();
        }
        return baseSelect()
                .where(TEST_RUNS.PROJECT_ID.eq(run.projectId())
                        .and(TEST_RUNS.TEST_BATCH_ID.eq(run.testBatchId()))
                        .and(TEST_RUNS.TEST_BATCH_ROLE.eq(peerRole.name()))
                        .and(TEST_RUNS.ID.ne(run.id())))
                .orderBy(TEST_RUNS.STARTED_AT.desc().nullsLast(), TEST_RUNS.ID.desc())
                .limit(1)
                .fetchOptional(this::map);
    }

    public boolean buildRunExists(UUID projectId, UUID buildRunId) {
        if (buildRunId == null) {
            return true;
        }
        return dsl.fetchExists(BUILD_RUNS, BUILD_RUNS.ID.eq(buildRunId).and(BUILD_RUNS.PROJECT_ID.eq(projectId)));
    }

    public long count(UUID projectId, AutomatedTestListRequest request) {
        return dsl.selectCount()
                .from(TEST_RUNS)
                .where(filter(projectId, request))
                .fetchOne(0, long.class);
    }

    public List<AutomatedTestRunView> list(UUID projectId, AutomatedTestListRequest request) {
        int page = request.normalizedPage();
        int pageSize = request.normalizedPageSize();
        return baseSelect()
                .where(filter(projectId, request))
                .orderBy(orderBy(request))
                .limit(pageSize)
                .offset((page - 1) * pageSize)
                .fetch(this::map);
    }

    public Optional<AutomatedTestRunView> findLatest(UUID projectId, UUID sourceRevisionId, Long environmentConfigVersion) {
        Condition condition = TEST_RUNS.PROJECT_ID.eq(projectId);
        if (sourceRevisionId != null) {
            condition = condition.and(TEST_RUNS.SOURCE_REVISION_ID.eq(sourceRevisionId));
        }
        if (environmentConfigVersion != null) {
            condition = condition.and(TEST_RUNS.ENVIRONMENT_CONFIG_VERSION.eq(environmentConfigVersion));
        }
        return baseSelect()
                .where(condition)
                .orderBy(activeFirst(TEST_RUNS.STATUS), TASKS.CREATED_AT.desc().nullsLast(), TEST_RUNS.ID.desc())
                .limit(1)
                .fetchOptional(this::map);
    }

    public void markRunning(UUID id) {
        dsl.update(TEST_RUNS)
                .set(TEST_RUNS.STATUS, TaskStatus.RUNNING.name())
                .set(TEST_RUNS.STARTED_AT, OffsetDateTime.now())
                .where(TEST_RUNS.ID.eq(id))
                .execute();
    }

    public void finish(
            UUID id,
            TaskStatus status,
            Integer exitCode,
            UUID stdoutLogId,
            UUID stderrLogId,
            UUID combinedLogId,
            String outputSummary,
            List<Map<String, Object>> reportArtifacts
    ) {
        dsl.update(TEST_RUNS)
                .set(TEST_RUNS.STATUS, status.name())
                .set(TEST_RUNS.EXIT_CODE, exitCode)
                .set(TEST_RUNS.STDOUT_LOG_ID, stdoutLogId)
                .set(TEST_RUNS.STDERR_LOG_ID, stderrLogId)
                .set(TEST_RUNS.COMBINED_LOG_ID, combinedLogId)
                .set(OUTPUT_SUMMARY, blankToNull(outputSummary))
                .set(REPORT_ARTIFACTS, toJsonb(reportArtifacts))
                .set(TEST_RUNS.FINISHED_AT, OffsetDateTime.now())
                .where(TEST_RUNS.ID.eq(id))
                .execute();
    }

    public void updateStats(UUID id, Integer passedCount, Integer failedCount, Integer skippedCount) {
        dsl.update(TEST_RUNS)
                .set(TEST_RUNS.PASSED_COUNT, passedCount)
                .set(TEST_RUNS.FAILED_COUNT, failedCount)
                .set(TEST_RUNS.SKIPPED_COUNT, skippedCount)
                .where(TEST_RUNS.ID.eq(id))
                .execute();
    }

    private org.jooq.SelectJoinStep<Record> baseSelect() {
        return dsl.select(TEST_RUNS.fields())
                .select(ENVIRONMENTS.NAME)
                .from(TEST_RUNS)
                .leftJoin(ENVIRONMENTS).on(ENVIRONMENTS.ID.eq(TEST_RUNS.ENVIRONMENT_ID))
                .leftJoin(TASKS).on(TASKS.ID.eq(TEST_RUNS.TASK_ID));
    }

    private AutomatedTestRunView map(Record record) {
        TestRunsRecord run = record.into(TEST_RUNS);
        return new AutomatedTestRunView(
                run.getId(),
                run.getProjectId(),
                run.getTaskId(),
                run.getBuildRunId(),
                run.getSourceRevisionId(),
                run.getEnvironmentId(),
                run.getEnvironmentConfigVersion(),
                run.getTestBatchId(),
                run.getTestBatchRole() == null ? null : TestBatchRole.valueOf(run.getTestBatchRole()),
                record.get(ENVIRONMENTS.NAME),
                run.getCommand(),
                run.getWorkingDirectory(),
                run.getTimeoutSeconds(),
                run.getExitCode(),
                run.getPassedCount(),
                run.getFailedCount(),
                run.getSkippedCount(),
                TaskStatus.valueOf(run.getStatus()),
                run.getStdoutLogId(),
                run.getStderrLogId(),
                run.getCombinedLogId(),
                record.get(OUTPUT_SUMMARY),
                fromReportArtifacts(record.get(REPORT_ARTIFACTS)),
                run.getStartedAt(),
                run.getFinishedAt()
        );
    }

    private Condition filter(UUID projectId, AutomatedTestListRequest request) {
        Condition condition = TEST_RUNS.PROJECT_ID.eq(projectId);
        if (request.status() != null) {
            condition = condition.and(TEST_RUNS.STATUS.eq(request.status().name()));
        }
        if (request.environmentId() != null) {
            condition = condition.and(TEST_RUNS.ENVIRONMENT_ID.eq(request.environmentId()));
        }
        if (request.sourceRevisionId() != null) {
            condition = condition.and(TEST_RUNS.SOURCE_REVISION_ID.eq(request.sourceRevisionId()));
        }
        return condition;
    }

    private OrderField<?>[] orderBy(AutomatedTestListRequest request) {
        boolean asc = "asc".equalsIgnoreCase(request.sortDirection());
        Field<?> field = switch (request.sortBy() == null ? "" : request.sortBy()) {
            case "status" -> TEST_RUNS.STATUS;
            case "finishedAt" -> TEST_RUNS.FINISHED_AT;
            case "createdAt" -> TASKS.CREATED_AT;
            default -> TEST_RUNS.STARTED_AT;
        };
        return new OrderField<?>[] {
                asc ? field.asc().nullsLast() : field.desc().nullsLast(),
                TEST_RUNS.ID.desc()
        };
    }

    private JSONB toJsonb(List<Map<String, Object>> value) {
        try {
            return JSONB.valueOf(objectMapper.writeValueAsString(value == null ? List.of() : value));
        } catch (JsonProcessingException ex) {
            return JSONB.valueOf("[]");
        }
    }

    private List<Map<String, Object>> fromReportArtifacts(JSONB value) {
        if (value == null || value.data() == null || value.data().isBlank()) {
            return List.of();
        }
        try {
            return objectMapper.readValue(value.data(), REPORT_ARTIFACTS_TYPE);
        } catch (JsonProcessingException ex) {
            return List.of();
        }
    }

    private String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }
}
