package cn.rvport.backend.optimization;

import static cn.rvport.backend.jooq.tables.TestRuns.TEST_RUNS;
import static cn.rvport.backend.jooq.tables.Tasks.TASKS;
import static cn.rvport.backend.jooq.tables.TestComparisonRuns.TEST_COMPARISON_RUNS;

import cn.rvport.backend.jooq.tables.records.TestRunsRecord;
import cn.rvport.backend.jooq.tables.records.TestComparisonRunsRecord;
import java.time.OffsetDateTime;
import java.util.Optional;
import java.util.UUID;
import org.jooq.Condition;
import org.jooq.DSLContext;
import org.jooq.Field;
import org.jooq.impl.DSL;
import org.springframework.stereotype.Repository;

/** 当前验证证据的有界查询；历史聚合不使用这些结果回填缺口。 */
@Repository
public class OptimizationEvidenceRepository {
    private final DSLContext dsl;

    public OptimizationEvidenceRepository(DSLContext dsl) {
        this.dsl = dsl;
    }

    public record TestEvidence(TestRunsRecord run, OffsetDateTime createdAt) { }

    public Optional<TestEvidence> candidate(UUID project, UUID source, long version, UUID sourceEnv, UUID targetEnv) {
        var batchKey = DSL.coalesce(TEST_RUNS.TEST_BATCH_ID, TEST_RUNS.ID);
        return dsl.select(TEST_RUNS.fields()).select(TASKS.CREATED_AT)
                .from(TEST_RUNS).leftJoin(TASKS).on(TASKS.ID.eq(TEST_RUNS.TASK_ID))
                .where(context(project, source, version, sourceEnv, targetEnv))
                .orderBy(DSL.min(activeFirst(TEST_RUNS.STATUS)).over(DSL.partitionBy(batchKey)).asc(),
                        DSL.max(TASKS.CREATED_AT).over(DSL.partitionBy(batchKey)).desc().nullsLast(),
                        batchKey.desc(), activeFirst(TEST_RUNS.STATUS), TASKS.CREATED_AT.desc().nullsLast(), TEST_RUNS.ID.desc())
                .limit(1).fetchOptional(r -> new TestEvidence(r.into(TEST_RUNS), r.get(TASKS.CREATED_AT)));
    }

    public Optional<TestEvidence> side(UUID project, UUID source, long version, UUID sourceEnv, UUID targetEnv,
                                      UUID batch, String role) {
        return dsl.select(TEST_RUNS.fields()).select(TASKS.CREATED_AT)
                .from(TEST_RUNS).leftJoin(TASKS).on(TASKS.ID.eq(TEST_RUNS.TASK_ID))
                .where(context(project, source, version, sourceEnv, targetEnv)
                        .and(TEST_RUNS.TEST_BATCH_ID.eq(batch)).and(TEST_RUNS.TEST_BATCH_ROLE.eq(role)))
                .orderBy(activeFirst(TEST_RUNS.STATUS), TASKS.CREATED_AT.desc().nullsLast(), TEST_RUNS.ID.desc())
                .limit(1).fetchOptional(r -> new TestEvidence(r.into(TEST_RUNS), r.get(TASKS.CREATED_AT)));
    }

    public Optional<TestComparisonRunsRecord> comparison(UUID project, UUID batch, UUID sourceTest, UUID targetTest) {
        return dsl.selectFrom(TEST_COMPARISON_RUNS)
                .where(TEST_COMPARISON_RUNS.PROJECT_ID.eq(project)
                        .and(TEST_COMPARISON_RUNS.TEST_BATCH_ID.eq(batch))
                        .and(TEST_COMPARISON_RUNS.SOURCE_TEST_RUN_ID.eq(sourceTest))
                        .and(TEST_COMPARISON_RUNS.TARGET_TEST_RUN_ID.eq(targetTest)))
                .orderBy(activeFirst(TEST_COMPARISON_RUNS.STATUS), TEST_COMPARISON_RUNS.CREATED_AT.desc(), TEST_COMPARISON_RUNS.ID.desc())
                .limit(1).fetchOptional();
    }

    private Condition context(UUID project, UUID source, long version, UUID sourceEnv, UUID targetEnv) {
        return TEST_RUNS.PROJECT_ID.eq(project).and(TEST_RUNS.SOURCE_REVISION_ID.eq(source))
                .and(TEST_RUNS.ENVIRONMENT_CONFIG_VERSION.eq(version))
                .and(TEST_RUNS.ENVIRONMENT_ID.in(sourceEnv, targetEnv));
    }

    private Field<Integer> activeFirst(Field<String> status) {
        return DSL.when(status.in("PENDING", "QUEUED", "RUNNING"), 0).otherwise(1);
    }
}
