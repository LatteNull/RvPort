package cn.rvport.backend.optimization;

import static cn.rvport.backend.jooq.tables.TestRuns.TEST_RUNS;
import static cn.rvport.backend.jooq.tables.Tasks.TASKS;
import static org.assertj.core.api.Assertions.assertThat;

import cn.rvport.backend.jooq.tables.records.TestComparisonRunsRecord;
import cn.rvport.backend.testfixture.JooqMockDatabase;
import java.time.OffsetDateTime;
import java.util.*;
import org.jooq.Field;
import org.junit.jupiter.api.Test;

class OptimizationEvidenceRepositoryTests {
    @Test void selectsCandidateBatchBeforeCheckingCompletenessAndSelectsEachRoleWithExactContext() throws Exception {
        UUID project = UUID.randomUUID(), source = UUID.randomUUID(), sourceEnv = UUID.randomUUID(), targetEnv = UUID.randomUUID();
        UUID batch = UUID.randomUUID(), test = UUID.randomUUID();
        var now = OffsetDateTime.parse("2026-10-29T00:00:00Z");
        try (var db = new JooqMockDatabase()) {
            var repo = new OptimizationEvidenceRepository(db.dsl());
            var fields = new ArrayList<Field<?>>(Arrays.asList(TEST_RUNS.fields())); fields.add(TASKS.CREATED_AT);
            var record = db.dsl().newRecord(fields);
            record.set(TEST_RUNS.ID, test); record.set(TEST_RUNS.TEST_BATCH_ID, batch); record.set(TEST_RUNS.STATUS, "QUEUED");
            record.set(TASKS.CREATED_AT, now);
            db.enqueueRecord(record).enqueueRecord(record);
            var candidate = repo.candidate(project, source, 7L, sourceEnv, targetEnv).orElseThrow();
            assertThat(candidate.createdAt()).isEqualTo(now);
            assertThat(candidate.run().getId()).isEqualTo(test);
            var sql = db.lastExecution().normalizedSql();
            assertThat(sql).contains("project_id =", "source_revision_id =", "environment_config_version =", "environment_id in", "partition by", "max(", "min(", "fetch next");
            assertThat(db.lastExecution().bindings()).contains(project, source, 7L, sourceEnv, targetEnv);
            assertThat(sql).doesNotContain("started_at desc", "status = ?");
            assertThat(repo.side(project, source, 7L, sourceEnv, targetEnv, batch, "SOURCE").orElseThrow().run().getTestBatchId()).isEqualTo(batch);
            assertThat(db.lastExecution().normalizedSql()).contains("test_batch_id =", "test_batch_role =", "created_at desc nulls last", "id desc");
            assertThat(db.lastExecution().bindings()).contains(batch, "SOURCE", project, source, 7L, sourceEnv, targetEnv);
            db.verifyComplete();
        }
    }

    @Test void comparisonRequiresBothExactInputsAndNeverFiltersOutFailures() throws Exception {
        try (var db = new JooqMockDatabase()) {
            var repo = new OptimizationEvidenceRepository(db.dsl());
            UUID project = UUID.randomUUID(), batch = UUID.randomUUID(), left = UUID.randomUUID(), right = UUID.randomUUID();
            var record = new TestComparisonRunsRecord(); record.setId(UUID.randomUUID()); record.setStatus("FAILED");
            db.enqueueRecord(record);
            assertThat(repo.comparison(project, batch, left, right).orElseThrow().getStatus()).isEqualTo("FAILED");
            assertThat(db.lastExecution().normalizedSql()).contains("project_id =", "test_batch_id =", "source_test_run_id =", "target_test_run_id =", "case when", "created_at desc", "id desc")
                    .doesNotContain(" or ", "overall_status =");
            assertThat(db.lastExecution().bindings()).contains(project, batch, left, right);
            db.verifyComplete();
        }
    }
}
