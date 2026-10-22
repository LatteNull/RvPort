package cn.rvport.backend.worker;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;

import cn.rvport.backend.task.TaskEventService;
import cn.rvport.backend.task.TaskRepository;
import cn.rvport.backend.task.TaskRuntimeHandleRepository;
import cn.rvport.backend.task.TaskRuntimeHandleStatus;
import cn.rvport.backend.task.TaskSecretPayloadService;
import cn.rvport.backend.task.TaskStatus;
import java.time.OffsetDateTime;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import liquibase.integration.spring.SpringLiquibase;
import org.jooq.DSLContext;
import org.jooq.SQLDialect;
import org.jooq.impl.DSL;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.aop.framework.ProxyFactory;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.jdbc.datasource.TransactionAwareDataSourceProxy;
import org.springframework.transaction.annotation.AnnotationTransactionAttributeSource;
import org.springframework.transaction.interceptor.TransactionInterceptor;

/** 独立 PostgreSQL 事务验证；不属于无外部依赖的单元测试套件。 */
@EnabledIfEnvironmentVariable(named = "RVPORT_FINALIZATION_DB_TEST", matches = "true")
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class TaskAttemptDatabaseIT {
    private DSLContext db;
    private DataSourceTransactionManager transactions;
    private TaskRepository tasks;
    private TaskRuntimeHandleRepository handles;
    private WorkerInstanceRepository workers;
    private TaskAttemptService attempts;
    private TaskDomainFinalizationService domains;
    private WorkerCleanupItemService cleanup;
    private UUID taskId;
    private UUID runId;
    private String workerId;
    private TaskAttemptService.Claim claim;
    private final OffsetDateTime cutoff = OffsetDateTime.now().minusMinutes(5);

    @BeforeAll
    void migrate() throws Exception {
        DriverManagerDataSource source = new DriverManagerDataSource(
                System.getenv("RVPORT_FINALIZATION_JDBC_URL"), "fixture", "fixture-test-only");
        SpringLiquibase liquibase = new SpringLiquibase();
        liquibase.setDataSource(source);
        liquibase.setChangeLog("classpath:/db/changelog/db.changelog-master.yaml");
        liquibase.afterPropertiesSet();
        transactions = new DataSourceTransactionManager(source);
        transactions.setDefaultTimeout(20);
        db = DSL.using(new TransactionAwareDataSourceProxy(source), SQLDialect.POSTGRES);
        tasks = new TaskRepository(db);
        handles = new TaskRuntimeHandleRepository(db);
        workers = new WorkerInstanceRepository(db);
        TaskEventService events = mock(TaskEventService.class);
        attempts = transactional(new TaskAttemptService(tasks, handles, workers));
        domains = transactional(new TaskDomainFinalizationService(
                new TaskDomainFinalizationRepository(db), tasks, events));
        cleanup = transactional(new WorkerCleanupItemService(workers, handles, tasks, events,
                mock(TaskSecretPayloadService.class), domains));
    }

    @BeforeEach
    void fixture() {
        UUID user = db.fetchOne("select id from users limit 1").get(0, UUID.class);
        UUID project = UUID.randomUUID();
        UUID revision = UUID.randomUUID();
        taskId = UUID.randomUUID();
        runId = UUID.randomUUID();
        workerId = "fixture-" + UUID.randomUUID();
        db.execute("insert into projects(id,name,stage,status,created_by) values (?,?,'PROJECT_CREATED','ACTIVE',?)",
                project, workerId, user);
        db.execute("insert into source_revisions(id,project_id,revision_type,created_by) values (?,?,'GIT',?)",
                revision, project, user);
        db.execute("insert into tasks(id,project_id,type,status,input_snapshot,created_by) values (?,?,'KB_SCAN','QUEUED','{}',?)",
                taskId, project, user);
        db.execute("insert into kb_scan_runs(id,project_id,task_id,source_revision_id,scope,status,summary) values (?,?,?,?,'{}','RUNNING','{\"retained\":true}')",
                runId, project, taskId, revision);
        workers.upsertHeartbeat(workerId, "fixture", 1, "test", 1, 1, 1);
        claim = attempts.claim(taskId, workerId);
        db.execute("update worker_instances set last_heartbeat_at=now()-interval '1 hour' where instance_id=?", workerId);
    }

    @Test
    void cleanupWinsAndRejectsLatePublication() {
        assertThat(cleanup.reconcile(workerId, cutoff).failedTasks()).hasSize(1);
        assertThatThrownBy(() -> attempts.publish(taskId, claim.handle().id(), () -> {
            db.execute("update kb_scan_runs set status='SUCCEEDED' where id=?", runId);
            return null;
        })).isInstanceOf(TaskAttemptLostException.class);
        assertThat(status()).isEqualTo("FAILED");
        assertThat(db.fetchOne("select summary->>'retained',summary->>'errorCode',finished_at from kb_scan_runs where id=?", runId)
                .get(0, String.class)).isEqualTo("true");
        assertThat(db.fetchOne("select summary->>'errorCode' from kb_scan_runs where id=?", runId).get(0, String.class))
                .isEqualTo("WORKER_LOST");
        assertThat(cleanup.reconcile(workerId, cutoff).failedTasks()).isEmpty();
    }

    @Test
    void publicationHoldsTaskLockAndCleanupPreservesCompletedRun() throws Exception {
        CountDownLatch locked = new CountDownLatch(1);
        CountDownLatch release = new CountDownLatch(1);
        try (var pool = Executors.newFixedThreadPool(2)) {
            var published = pool.submit(() -> attempts.publish(taskId, claim.handle().id(), () -> {
                db.execute("update kb_scan_runs set status='SUCCEEDED',finished_at=now() where id=?", runId);
                locked.countDown();
                await(release);
                return true;
            }));
            assertThat(locked.await(10, TimeUnit.SECONDS)).isTrue();
            var cleaned = pool.submit(() -> cleanup.reconcile(workerId, cutoff));
            try {
                assertThatThrownBy(() -> cleaned.get(200, TimeUnit.MILLISECONDS))
                        .isInstanceOf(java.util.concurrent.TimeoutException.class);
            } finally {
                release.countDown();
            }
            assertThat(published.get(10, TimeUnit.SECONDS)).isTrue();
            assertThat(cleaned.get(10, TimeUnit.SECONDS).failedTasks()).hasSize(1);
        }
        assertThat(status()).isEqualTo("SUCCEEDED");
        assertThat(tasks.findById(taskId).orElseThrow().status()).isEqualTo(TaskStatus.FAILED);
    }

    @Test
    void twoCleanersOnlyFinalizeOnce() throws Exception {
        CountDownLatch start = new CountDownLatch(1);
        try (var pool = Executors.newFixedThreadPool(2)) {
            var first = pool.submit(() -> { await(start); return cleanup.reconcile(workerId, cutoff); });
            var second = pool.submit(() -> { await(start); return cleanup.reconcile(workerId, cutoff); });
            start.countDown();
            assertThat(first.get(10, TimeUnit.SECONDS).failedTasks().size()
                    + second.get(10, TimeUnit.SECONDS).failedTasks().size()).isEqualTo(1);
        }
        assertThat(status()).isEqualTo("FAILED");
    }

    @Test
    void restoredHeartbeatPreventsCleanup() {
        workers.upsertHeartbeat(workerId, "fixture", 1, "test", 1, 1, 1);
        assertThat(cleanup.reconcile(workerId, cutoff).failedTasks()).isEmpty();
        assertThat(status()).isEqualTo("RUNNING");
        assertThat(attempts.publish(taskId, claim.handle().id(), () -> true)).isTrue();
    }

    @Test
    void failedPublicationRollsBackAndRetryGetsDifferentIdentity() {
        assertThatThrownBy(() -> attempts.publish(taskId, claim.handle().id(), () -> {
            db.execute("update kb_scan_runs set status='SUCCEEDED' where id=?", runId);
            throw new IllegalStateException("fixture rollback");
        })).isInstanceOf(IllegalStateException.class);
        assertThat(status()).isEqualTo("RUNNING");
        attempts.publish(taskId, claim.handle().id(), () -> {
            tasks.markRetry(taskId, 1, "retry", "TEST_ERROR", "fixture");
            handles.markError(claim.handle().id(), TaskRuntimeHandleStatus.FAILED, "TEST_ERROR", "fixture");
            return null;
        });
        TaskAttemptService.Claim next = attempts.claim(taskId, workerId);
        assertThat(next.handle().id()).isNotEqualTo(claim.handle().id());
        assertThatThrownBy(() -> attempts.publish(taskId, claim.handle().id(), () -> true))
                .isInstanceOf(TaskAttemptLostException.class);
        assertThat(attempts.publish(taskId, next.handle().id(), () -> true)).isTrue();
    }

    @Test
    void domainErrorRollsBackTaskAndHandleCleanup() {
        TaskDomainFinalizationService failing = mock(TaskDomainFinalizationService.class);
        org.mockito.Mockito.doThrow(new IllegalStateException("fixture write failure")).when(failing).finish(org.mockito.ArgumentMatchers.any());
        WorkerCleanupItemService broken = transactional(new WorkerCleanupItemService(workers, handles, tasks,
                mock(TaskEventService.class), mock(TaskSecretPayloadService.class), failing));
        assertThatThrownBy(() -> broken.reconcile(workerId, cutoff)).isInstanceOf(IllegalStateException.class);
        assertThat(tasks.findById(taskId).orElseThrow().status()).isEqualTo(TaskStatus.RUNNING);
        assertThat(handles.findActiveByTaskId(taskId).orElseThrow().id()).isEqualTo(claim.handle().id());
        assertThat(status()).isEqualTo("RUNNING");
    }

    @Test
    void historyReconcilesWithoutWorkerAndPreservesSucceededTaskForAudit() {
        tasks.completeIfActive(taskId, TaskStatus.TIMEOUT, "timeout", "TASK_TIMEOUT", "timeout");
        handles.markTerminated(claim.handle().id(), TaskRuntimeHandleStatus.TERMINATED);
        db.execute("delete from worker_instances where instance_id=?", workerId);
        assertThat(domains.reconcile(taskId)).isEqualTo(1);
        assertThat(status()).isEqualTo("TIMEOUT");
        assertThat(domains.reconcile(taskId)).isZero();
        db.execute("update tasks set status='SUCCEEDED' where id=?", taskId);
        db.execute("update kb_scan_runs set status='RUNNING' where id=?", runId);
        assertThat(domains.reconcile(taskId)).isZero();
        assertThat(status()).isEqualTo("RUNNING");
    }

    private String status() {
        return db.fetchOne("select status from kb_scan_runs where id=?", runId).get(0, String.class);
    }

    @SuppressWarnings("unchecked")
    private <T> T transactional(T target) {
        ProxyFactory proxy = new ProxyFactory(target);
        proxy.setProxyTargetClass(true);
        proxy.addAdvice(new TransactionInterceptor(transactions, new AnnotationTransactionAttributeSource(false)));
        return (T) proxy.getProxy();
    }

    private static void await(CountDownLatch latch) {
        try {
            if (!latch.await(10, TimeUnit.SECONDS)) {
                throw new IllegalStateException("fixture latch timed out");
            }
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException(ex);
        }
    }
}
