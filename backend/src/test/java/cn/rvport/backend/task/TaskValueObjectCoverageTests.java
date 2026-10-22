package cn.rvport.backend.task;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.jooq.tables.records.TaskEventsRecord;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class TaskValueObjectCoverageTests {

    @Test
    void taskEventResourceUsesTaskFallbacksAndOmitsEmptyValues() {
        UUID taskId = UUID.randomUUID();
        UUID projectId = UUID.randomUUID();
        TaskView task = task(taskId, projectId, null, null);
        TaskEventResource resource = TaskEventResource.fromTask(task);
        assertThat(resource.type()).isEqualTo(task.type());
        assertThat(resource.id()).isEqualTo(taskId);
        assertThat(resource.toMap()).containsEntry("type", task.type()).containsEntry("id", taskId)
                .containsEntry("mode", "mode").containsEntry("environmentRole", "SOURCE_X86");
        assertThat(TaskEventResource.fromTask(null)).isEqualTo(TaskEventResource.empty());
        assertThat(TaskEventResource.empty().toMap()).isEmpty();

        UUID resourceId = UUID.randomUUID();
        TaskEventResource explicit = TaskEventResource.fromTask(task(taskId, projectId, resourceId, "source_revision"));
        assertThat(explicit.id()).isEqualTo(resourceId);
        assertThat(explicit.type()).isEqualTo("source_revision");
        assertThat(new TaskEventResource(" ", null, "mode", "role").toMap())
                .containsOnly(Map.entry("mode", "mode"), Map.entry("environmentRole", "role"));
    }

    @Test
    void logSanitizerHandlesNullBlankShortSensitiveAndOversizedValues() {
        assertThat(TaskLogSanitizer.safeExcerpt(null)).isEmpty();
        assertThat(TaskLogSanitizer.safeExcerpt(" ")).isEmpty();
        assertThat(TaskLogSanitizer.safeContent(null)).isEmpty();
        assertThat(TaskLogSanitizer.safeContent("")).isEmpty();
        assertThat(TaskLogSanitizer.safeExcerpt(" password=secret\nvisible "))
                .isEqualTo("password=**** visible");
        assertThat(TaskLogSanitizer.safeExcerpt("x".repeat(600)))
                .hasSize(TaskLogSanitizer.MAX_EXCERPT_LENGTH);
    }

    @Test
    void incrementRequestAcceptsDefaultsAndBoundsAndRejectsInvalidNumbers() {
        assertThat(TaskLogIncrementRequest.from(null, null))
                .isEqualTo(new TaskLogIncrementRequest(0, TaskLogIncrementRequest.DEFAULT_LIMIT));
        assertThat(TaskLogIncrementRequest.from(" 7 ", "1000"))
                .isEqualTo(new TaskLogIncrementRequest(7, 1000));
        assertThat(TaskLogIncrementRequest.parseCursor(" ")).isZero();
        for (String cursor : new String[]{"-1", "bad"}) {
            assertThatThrownBy(() -> TaskLogIncrementRequest.from(cursor, "1"))
                    .isInstanceOf(ApiException.class);
        }
        for (String limit : new String[]{"0", "1001", "2147483648", "bad"}) {
            assertThatThrownBy(() -> TaskLogIncrementRequest.from("0", limit))
                    .isInstanceOf(ApiException.class);
        }
    }

    @Test
    void taskListRequestNormalizesOnlyMissingPagination() {
        assertThat(new TaskListRequest(null, null, null, null).normalizedPage()).isEqualTo(1);
        assertThat(new TaskListRequest(null, null, null, null).normalizedPageSize()).isEqualTo(20);
        assertThat(new TaskListRequest(TaskStatus.RUNNING, "TYPE", 3, 40).normalizedPage()).isEqualTo(3);
        assertThat(new TaskListRequest(TaskStatus.RUNNING, "TYPE", 3, 40).normalizedPageSize()).isEqualTo(40);
    }

    @Test
    void scriptExecutionListRequestNormalizesDefaultsBlankSortAndExplicitValues() {
        ScriptExecutionListRequest defaults = new ScriptExecutionListRequest(
                null, null, null, null, null, null);
        ScriptExecutionListRequest blankSort = new ScriptExecutionListRequest(
                null, null, null, "   ", 2, 50);
        ScriptExecutionListRequest explicit = new ScriptExecutionListRequest(
                ScriptExecutionStatus.SUCCEEDED, UUID.randomUUID(), "build", " status.asc ", 3, 100);

        assertThat(defaults.normalizedPage()).isEqualTo(1);
        assertThat(defaults.normalizedPageSize()).isEqualTo(20);
        assertThat(defaults.normalizedSort()).isEqualTo("createdAt.desc");
        assertThat(blankSort.normalizedSort()).isEqualTo("createdAt.desc");
        assertThat(blankSort.normalizedPage()).isEqualTo(2);
        assertThat(blankSort.normalizedPageSize()).isEqualTo(50);
        assertThat(explicit.normalizedSort()).isEqualTo("status.asc");
        assertThat(explicit.normalizedPage()).isEqualTo(3);
        assertThat(explicit.normalizedPageSize()).isEqualTo(100);
    }

    @Test
    void taskEventViewUsesFallbacksForOptionalEventMetadata() {
        UUID projectId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        OffsetDateTime occurredAt = OffsetDateTime.now();
        TaskEventsRecord record = new TaskEventsRecord();
        record.setId(12L);
        record.setEventId("12");
        record.setProjectId(projectId);
        record.setTaskId(taskId);
        record.setEventType("task.progress");
        record.setProgress(25);
        record.setOccurredAt(occurredAt);

        TaskEventView fallback = TaskEventView.from(record, "BUILD", "BUILD_STAGE", null, null);
        assertThat(fallback.status()).isNull();
        assertThat(fallback.stageId()).isEqualTo("BUILD_STAGE");
        assertThat(fallback.resource()).isEqualTo(TaskEventResource.empty());
        assertThat(fallback.changedFields()).isEmpty();

        record.setStatus(TaskStatus.RUNNING.name());
        record.setStageId("EVENT_STAGE");
        TaskEventResource resource = TaskEventResource.of("task", taskId);
        TaskEventView explicit = TaskEventView.from(record, "BUILD", "BUILD_STAGE", resource, List.of("status"));
        assertThat(explicit.status()).isEqualTo(TaskStatus.RUNNING);
        assertThat(explicit.stageId()).isEqualTo("EVENT_STAGE");
        assertThat(explicit.resource()).isEqualTo(resource);
        assertThat(explicit.changedFields()).containsExactly("status");
    }

    @Test
    void taskEventResourceFallsBackForBlankExplicitTypeAndKeepsNonStringValues() {
        UUID taskId = UUID.randomUUID();
        UUID projectId = UUID.randomUUID();

        TaskEventResource resource = TaskEventResource.fromTask(task(taskId, projectId, null, " "));

        assertThat(resource.type()).isEqualTo("KB_SCAN");
        assertThat(TaskEventResource.of("task", taskId).toMap())
                .containsExactly(Map.entry("type", "task"), Map.entry("id", taskId));
    }

    private TaskView task(UUID id, UUID projectId, UUID resourceId, String resourceType) {
        return new TaskView(
                id, projectId, "KB_SCAN", TaskStatus.RUNNING, 10, "running", UUID.randomUUID(),
                OffsetDateTime.now(), OffsetDateTime.now(), OffsetDateTime.now(), null, 60,
                null, null, 0, "KB_SCAN", resourceType, resourceId, "mode", "SOURCE_X86");
    }
}
