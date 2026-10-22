package cn.rvport.backend.task;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.config.RvPortProperties;
import cn.rvport.backend.jooq.tables.records.TaskLogsRecord;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.OffsetDateTime;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.mockito.ArgumentCaptor;

class TaskLogServiceTests {

    @TempDir
    private Path tempDir;

    @Test
    void appendsLogFileAndStoresRelativeMetadata() throws Exception {
        TaskLogRepository repository = org.mockito.Mockito.mock(TaskLogRepository.class);
        TaskLogService service = new TaskLogService(repository, properties(tempDir));
        UUID projectId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        ArgumentCaptor<String> pathCaptor = ArgumentCaptor.forClass(String.class);
        when(repository.findLatestRecord(taskId, TaskLogType.STDOUT)).thenReturn(Optional.empty());
        when(repository.create(eq(projectId), eq(taskId), eq(TaskLogType.STDOUT), pathCaptor.capture(), eq(5L), eq(1L), any(), eq("hello")))
                .thenAnswer(invocation -> new TaskLogResponse(
                        UUID.randomUUID(),
                        taskId,
                        projectId,
                        TaskLogType.STDOUT,
                        invocation.getArgument(4),
                        invocation.getArgument(5),
                        invocation.getArgument(6),
                        invocation.getArgument(7),
                        OffsetDateTime.now()
                ));

        Optional<TaskLogResponse> response = service.append(projectId, taskId, TaskLogType.STDOUT, "hello");

        assertThat(response).isPresent();
        assertThat(pathCaptor.getValue()).isEqualTo(taskId + "/stdout.log");
        assertThat(Path.of(pathCaptor.getValue()).isAbsolute()).isFalse();
        assertThat(Files.readString(tempDir.resolve(pathCaptor.getValue()))).isEqualTo("hello");
        assertThat(response.get().lineCount()).isEqualTo(1);
        assertThat(response.get().excerpt()).isEqualTo("hello");
    }

    @Test
    void skipsEmptyLogWithoutCreatingMetadata() {
        TaskLogRepository repository = org.mockito.Mockito.mock(TaskLogRepository.class);
        TaskLogService service = new TaskLogService(repository, properties(tempDir));

        Optional<TaskLogResponse> response = service.append(UUID.randomUUID(), UUID.randomUUID(), TaskLogType.TOOL, "");

        assertThat(response).isEmpty();
        verify(repository, never()).create(any(), any(), any(), any(), anyLong(), anyLong(), any(), any());
    }

    @Test
    void masksSensitiveExcerptAndTruncatesLongContent() {
        TaskLogRepository repository = org.mockito.Mockito.mock(TaskLogRepository.class);
        TaskLogService service = new TaskLogService(repository, properties(tempDir));
        UUID projectId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        ArgumentCaptor<String> excerptCaptor = ArgumentCaptor.forClass(String.class);
        when(repository.findLatestRecord(taskId, TaskLogType.TOOL)).thenReturn(Optional.empty());
        when(repository.create(eq(projectId), eq(taskId), eq(TaskLogType.TOOL), any(), anyLong(), anyLong(), any(), excerptCaptor.capture()))
                .thenAnswer(invocation -> new TaskLogResponse(UUID.randomUUID(), taskId, projectId, TaskLogType.TOOL,
                        invocation.getArgument(4), invocation.getArgument(5), invocation.getArgument(6), invocation.getArgument(7), OffsetDateTime.now()));

        service.append(projectId, taskId, TaskLogType.TOOL,
                "token=SecretToken password:SecretPassword {\"privateKey\":\"SecretKey\"} " + "x".repeat(700));

        assertThat(excerptCaptor.getValue())
                .doesNotContain("SecretToken")
                .doesNotContain("SecretPassword")
                .doesNotContain("SecretKey")
                .contains("token=****")
                .hasSize(500);
    }

    @Test
    void logWriteFailureUsesSafeTaskExecutionError() throws Exception {
        Path fileLogRoot = tempDir.resolve("logs-as-file");
        Files.writeString(fileLogRoot, "not a directory");
        TaskLogService service = new TaskLogService(org.mockito.Mockito.mock(TaskLogRepository.class), properties(fileLogRoot));

        assertThatThrownBy(() -> service.append(UUID.randomUUID(), UUID.randomUUID(), TaskLogType.STDERR, "boom"))
                .isInstanceOf(TaskExecutionException.class)
                .hasMessage("任务日志写入失败")
                .extracting("errorCode")
                .isEqualTo(TaskErrorCode.LOG_WRITE_FAILED);
    }

    @Test
    void downloadsLogWithinConfiguredLogDirectory() throws Exception {
        TaskLogRepository repository = org.mockito.Mockito.mock(TaskLogRepository.class);
        TaskLogService service = new TaskLogService(repository, properties(tempDir));
        UUID taskId = UUID.randomUUID();
        UUID logId = UUID.randomUUID();
        Path logFile = tempDir.resolve("task.log");
        Files.writeString(logFile, "hello");
        when(repository.findForTask(taskId, logId)).thenReturn(Optional.of(logRecord(taskId, logId, "task.log")));

        TaskLogService.DownloadableTaskLog log = service.download(taskId, logId);

        assertThat(log.filename()).isEqualTo("task.log");
        assertThat(log.resource().exists()).isTrue();
    }

    @Test
    void rejectsPathOutsideConfiguredLogDirectory() {
        TaskLogRepository repository = org.mockito.Mockito.mock(TaskLogRepository.class);
        TaskLogService service = new TaskLogService(repository, properties(tempDir));
        UUID taskId = UUID.randomUUID();
        UUID logId = UUID.randomUUID();
        when(repository.findForTask(taskId, logId)).thenReturn(Optional.of(logRecord(taskId, logId, "../secret.log")));

        assertThatThrownBy(() -> service.download(taskId, logId))
                .isInstanceOf(ApiException.class)
                .hasMessage("任务日志路径非法");
    }

    @Test
    void rejectsMissingLogRecordAndMissingLogFile() {
        TaskLogRepository repository = org.mockito.Mockito.mock(TaskLogRepository.class);
        TaskLogService service = new TaskLogService(repository, properties(tempDir));
        UUID taskId = UUID.randomUUID();
        UUID logId = UUID.randomUUID();
        when(repository.findForTask(taskId, logId)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.download(taskId, logId))
                .isInstanceOf(ApiException.class)
                .hasMessage("任务日志不存在");

        when(repository.findForTask(taskId, logId)).thenReturn(Optional.of(logRecord(taskId, logId, "missing.log")));
        assertThatThrownBy(() -> service.download(taskId, logId))
                .isInstanceOf(ApiException.class)
                .hasMessage("任务日志文件不存在");
    }

    @Test
    void downloadsNestedRelativeLogPath() throws Exception {
        TaskLogRepository repository = org.mockito.Mockito.mock(TaskLogRepository.class);
        TaskLogService service = new TaskLogService(repository, properties(tempDir));
        UUID taskId = UUID.randomUUID();
        UUID logId = UUID.randomUUID();
        Path nested = tempDir.resolve("tasks").resolve("task.log");
        Files.createDirectories(nested.getParent());
        Files.writeString(nested, "hello");
        when(repository.findForTask(taskId, logId)).thenReturn(Optional.of(logRecord(taskId, logId, "tasks/task.log")));

        TaskLogService.DownloadableTaskLog log = service.download(taskId, logId);

        assertThat(log.filename()).isEqualTo("task.log");
        assertThat(log.resource().exists()).isTrue();
    }

    @Test
    void readsDefaultLogContentForMultipleTypes() throws Exception {
        TaskLogRepository repository = org.mockito.Mockito.mock(TaskLogRepository.class);
        TaskLogService service = new TaskLogService(repository, properties(tempDir));
        UUID taskId = UUID.randomUUID();
        UUID mergedId = UUID.randomUUID();
        UUID stdoutId = UUID.randomUUID();
        Files.writeString(tempDir.resolve("merged.log"), "m1\nm2\nm3\n");
        Files.writeString(tempDir.resolve("stdout.log"), "s1\ns2\n");
        when(repository.findLatestRecord(taskId, TaskLogType.COMBINED))
                .thenReturn(Optional.of(logRecord(taskId, mergedId, TaskLogType.COMBINED, "merged.log")));
        when(repository.findLatestRecord(taskId, TaskLogType.STDOUT))
                .thenReturn(Optional.of(logRecord(taskId, stdoutId, TaskLogType.STDOUT, "stdout.log")));
        when(repository.findLatestRecord(taskId, TaskLogType.STDERR)).thenReturn(Optional.empty());

        TaskLogContentResponse response = service.content(taskId, TaskLogContentRequest.from(null, 2, null, null, null, null, null, null));

        assertThat(response.logs()).containsOnlyKeys("merged", "stdout", "stderr");
        assertThat(response.logs().get("merged").logId()).isEqualTo(mergedId);
        assertThat(response.logs().get("merged").content()).isEqualTo("m2\nm3");
        assertThat(response.logs().get("merged").totalLines()).isEqualTo(3);
        assertThat(response.logs().get("merged").hasMore()).isTrue();
        assertThat(response.logs().get("stdout").content()).isEqualTo("s1\ns2");
        assertThat(response.logs().get("stdout").totalLines()).isEqualTo(2);
        assertThat(response.logs().get("stderr").content()).isEmpty();
        assertThat(response.logs().get("stderr").totalLines()).isZero();
        assertThat(response.logs().get("stderr").hasMore()).isFalse();
    }

    @Test
    void readsPerTypeOffsetAndMasksSensitiveContent() throws Exception {
        TaskLogRepository repository = org.mockito.Mockito.mock(TaskLogRepository.class);
        TaskLogService service = new TaskLogService(repository, properties(tempDir));
        UUID taskId = UUID.randomUUID();
        UUID logId = UUID.randomUUID();
        Files.writeString(tempDir.resolve("stdout.log"), "line-1\ntoken=SecretToken\nline-3\n");
        when(repository.findLatestRecord(taskId, TaskLogType.STDOUT))
                .thenReturn(Optional.of(logRecord(taskId, logId, TaskLogType.STDOUT, "stdout.log")));

        TaskLogContentResponse response = service.content(taskId, TaskLogContentRequest.from("stdout", 3, null, 1L, null, null, 1, null));

        assertThat(response.logs()).containsOnlyKeys("stdout");
        assertThat(response.logs().get("stdout").offset()).isEqualTo(1);
        assertThat(response.logs().get("stdout").lines()).isEqualTo(1);
        assertThat(response.logs().get("stdout").totalLines()).isEqualTo(3);
        assertThat(response.logs().get("stdout").content()).isEqualTo("token=****");
        assertThat(response.logs().get("stdout").content()).doesNotContain("SecretToken");
    }

    @Test
    void appendsCumulativeLineCountAcrossChunksWithoutTrailingLineBreak() throws Exception {
        TaskLogRepository repository = org.mockito.Mockito.mock(TaskLogRepository.class);
        TaskLogService service = new TaskLogService(repository, properties(tempDir));
        UUID projectId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        when(repository.findLatestRecord(taskId, TaskLogType.STDOUT)).thenReturn(Optional.empty());
        when(repository.create(eq(projectId), eq(taskId), eq(TaskLogType.STDOUT), any(), anyLong(), anyLong(), any(), any()))
                .thenAnswer(invocation -> new TaskLogResponse(
                        UUID.randomUUID(),
                        taskId,
                        projectId,
                        TaskLogType.STDOUT,
                        invocation.getArgument(4),
                        invocation.getArgument(5),
                        invocation.getArgument(6),
                        invocation.getArgument(7),
                        OffsetDateTime.now()
                ));

        Optional<TaskLogResponse> first = service.append(projectId, taskId, TaskLogType.STDOUT, "one");
        TaskLogsRecord previous = logRecord(taskId, UUID.randomUUID(), TaskLogType.STDOUT, taskId + "/stdout.log");
        previous.setLineCount(first.orElseThrow().lineCount());
        when(repository.findLatestRecord(taskId, TaskLogType.STDOUT)).thenReturn(Optional.of(previous));
        Optional<TaskLogResponse> second = service.append(projectId, taskId, TaskLogType.STDOUT, "\ntwo\nthree");

        assertThat(first.orElseThrow().lineCount()).isEqualTo(1);
        assertThat(second.orElseThrow().lineCount()).isEqualTo(3);
        assertThat(Files.readString(tempDir.resolve(taskId + "/stdout.log"))).isEqualTo("one\ntwo\nthree");
    }

    @Test
    void fallsBackToCountingFileWhenLineCountMetadataIsMissing() throws Exception {
        TaskLogRepository repository = org.mockito.Mockito.mock(TaskLogRepository.class);
        TaskLogService service = new TaskLogService(repository, properties(tempDir));
        UUID taskId = UUID.randomUUID();
        UUID logId = UUID.randomUUID();
        Files.writeString(tempDir.resolve("stdout.log"), "one\ntwo\nthree");
        when(repository.findLatestRecord(taskId, TaskLogType.STDOUT))
                .thenReturn(Optional.of(logRecord(taskId, logId, TaskLogType.STDOUT, "stdout.log")));

        TaskLogContentResponse response = service.content(taskId, TaskLogContentRequest.from("stdout", 2, null, null, null, null, null, null));

        assertThat(response.logs().get("stdout").returnedLines()).isEqualTo(2);
        assertThat(response.logs().get("stdout").totalLines()).isEqualTo(3);
        assertThat(response.logs().get("stdout").hasMore()).isTrue();
    }

    @Test
    void rejectsUnixTraversalAndAbsolutePaths() {
        TaskLogRepository repository = org.mockito.Mockito.mock(TaskLogRepository.class);
        TaskLogService service = new TaskLogService(repository, properties(tempDir));
        UUID taskId = UUID.randomUUID();
        UUID logId = UUID.randomUUID();

        when(repository.findForTask(taskId, logId)).thenReturn(Optional.of(logRecord(taskId, logId, "../secret.log")));
        assertThatThrownBy(() -> service.download(taskId, logId))
                .isInstanceOf(ApiException.class)
                .hasMessage("任务日志路径非法");

        when(repository.findForTask(taskId, logId)).thenReturn(Optional.of(logRecord(taskId, logId, tempDir.getParent().resolve("secret.log").toString())));
        assertThatThrownBy(() -> service.download(taskId, logId))
                .isInstanceOf(ApiException.class)
                .hasMessage("任务日志路径非法");
    }

    private RvPortProperties properties(Path logDir) {
        return new RvPortProperties(
                new RvPortProperties.Runtime(logDir.toString(), tempDir.resolve("archives").toString(), tempDir.resolve("uploads").toString(), tempDir.resolve("sources").toString()),
                null,
                new RvPortProperties.Worker(false)
        );
    }

    private TaskLogsRecord logRecord(UUID taskId, UUID logId, String filePath) {
        return logRecord(taskId, logId, TaskLogType.STDOUT, filePath);
    }

    @Test
    void listsLogMetadataWithPagination() {
        TaskLogRepository repository = org.mockito.Mockito.mock(TaskLogRepository.class);
        TaskLogService service = new TaskLogService(repository, properties(tempDir));
        UUID taskId = UUID.randomUUID();
        TaskLogResponse item = new TaskLogResponse(UUID.randomUUID(), taskId, UUID.randomUUID(),
                TaskLogType.STDERR, 10L, 2L, "hash", "excerpt", OffsetDateTime.now());
        when(repository.count(taskId, TaskLogType.STDERR)).thenReturn(3L);
        when(repository.list(taskId, TaskLogType.STDERR, 2, 1)).thenReturn(java.util.List.of(item));

        var page = service.list(taskId, TaskLogType.STDERR, 2, 1);

        assertThat(page.items()).containsExactly(item);
        assertThat(page.total()).isEqualTo(3);
        assertThat(page.page()).isEqualTo(2);
    }

    @Test
    void readsTextWithByteLimitAndHandlesNullOrMissingFile() throws Exception {
        TaskLogRepository repository = org.mockito.Mockito.mock(TaskLogRepository.class);
        TaskLogService service = new TaskLogService(repository, properties(tempDir));
        UUID taskId = UUID.randomUUID();
        UUID logId = UUID.randomUUID();
        Files.writeString(tempDir.resolve("read.log"), "abcdef");
        when(repository.findForTask(taskId, logId)).thenReturn(Optional.of(logRecord(taskId, logId, "read.log")));

        assertThat(service.readText(taskId, null, 10)).isEmpty();
        assertThat(service.readText(taskId, logId, 3)).isEqualTo("abc");
        assertThat(service.readText(taskId, logId, 0)).isEmpty();

        UUID missingId = UUID.randomUUID();
        when(repository.findForTask(taskId, missingId))
                .thenReturn(Optional.of(logRecord(taskId, missingId, "missing.log")));
        assertThat(service.readText(taskId, missingId, 10)).isEmpty();
    }

    @Test
    void readTextRejectsMissingRecordAndUnsafePath() {
        TaskLogRepository repository = org.mockito.Mockito.mock(TaskLogRepository.class);
        TaskLogService service = new TaskLogService(repository, properties(tempDir));
        UUID taskId = UUID.randomUUID();
        UUID missingId = UUID.randomUUID();
        when(repository.findForTask(taskId, missingId)).thenReturn(Optional.empty());
        assertThatThrownBy(() -> service.readText(taskId, missingId, 10))
                .isInstanceOf(ApiException.class)
                .hasMessage("任务日志不存在");

        UUID unsafeId = UUID.randomUUID();
        when(repository.findForTask(taskId, unsafeId))
                .thenReturn(Optional.of(logRecord(taskId, unsafeId, "../outside.log")));
        assertThatThrownBy(() -> service.readText(taskId, unsafeId, 10))
                .isInstanceOf(ApiException.class)
                .hasMessage("任务日志路径非法");
    }

    @Test
    void readsSanitizedTailAndHandlesInputBoundaries() throws Exception {
        TaskLogRepository repository = org.mockito.Mockito.mock(TaskLogRepository.class);
        TaskLogService service = new TaskLogService(repository, properties(tempDir));
        UUID taskId = UUID.randomUUID();
        UUID logId = UUID.randomUUID();
        Files.writeString(tempDir.resolve("tail.log"), "first\ntoken=Secret\nlast\n");
        when(repository.findForTask(taskId, logId)).thenReturn(Optional.of(logRecord(taskId, logId, "tail.log")));

        assertThat(service.readTailText(taskId, null, 2)).isEmpty();
        assertThat(service.readTailText(taskId, logId, 0)).isEmpty();
        assertThat(service.readTailText(taskId, logId, 2)).isEqualTo("token=****\nlast");

        UUID missingFile = UUID.randomUUID();
        when(repository.findForTask(taskId, missingFile))
                .thenReturn(Optional.of(logRecord(taskId, missingFile, "none.log")));
        assertThat(service.readTailText(taskId, missingFile, 2)).isEmpty();
    }

    @Test
    void contentReturnsMetadataButNoTextWhenFileIsMissing() {
        TaskLogRepository repository = org.mockito.Mockito.mock(TaskLogRepository.class);
        TaskLogService service = new TaskLogService(repository, properties(tempDir));
        UUID taskId = UUID.randomUUID();
        UUID logId = UUID.randomUUID();
        when(repository.findLatestRecord(taskId, TaskLogType.STDOUT))
                .thenReturn(Optional.of(logRecord(taskId, logId, TaskLogType.STDOUT, "missing.log")));

        TaskLogContentResponse response = service.content(taskId,
                TaskLogContentRequest.from("stdout", 100, null, null, null, null, null, null));

        assertThat(response.logs().get("stdout").logId()).isEqualTo(logId);
        assertThat(response.logs().get("stdout").content()).isEmpty();
        assertThat(response.logs().get("stdout").totalLines()).isZero();
    }

    private TaskLogsRecord logRecord(UUID taskId, UUID logId, TaskLogType logType, String filePath) {
        TaskLogsRecord record = new TaskLogsRecord();
        record.setId(logId);
        record.setTaskId(taskId);
        record.setProjectId(UUID.randomUUID());
        record.setLogType(logType.name());
        record.setFilePath(filePath);
        record.setSizeBytes(5L);
        record.setExcerpt("hello");
        record.setCreatedAt(OffsetDateTime.now());
        return record;
    }
}
