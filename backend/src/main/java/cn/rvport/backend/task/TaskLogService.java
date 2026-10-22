package cn.rvport.backend.task;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.config.RvPortProperties;
import cn.rvport.backend.jooq.tables.records.TaskLogsRecord;
import java.net.MalformedURLException;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.SeekableByteChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.springframework.core.io.Resource;
import org.springframework.core.io.UrlResource;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class TaskLogService {

    private final TaskLogRepository taskLogRepository;
    private final Path logRoot;

    public TaskLogService(TaskLogRepository taskLogRepository, RvPortProperties properties) {
        this.taskLogRepository = taskLogRepository;
        this.logRoot = Path.of(properties.runtime().logDir()).toAbsolutePath().normalize();
    }

    @Transactional(readOnly = true)
    public PageResponse<TaskLogResponse> list(UUID taskId, TaskLogType logType, int page, int pageSize) {
        long total = taskLogRepository.count(taskId, logType);
        List<TaskLogResponse> items = taskLogRepository.list(taskId, logType, page, pageSize);
        return PageResponse.of(items, page, pageSize, total);
    }

    @Transactional(readOnly = true)
    public TaskLogContentResponse content(UUID taskId, TaskLogContentRequest contentRequest) {
        Map<String, TaskLogContentResponse.LogContent> logs = new LinkedHashMap<>();
        for (TaskLogContentRequest.Entry entry : contentRequest.entries()) {
            TaskLogContentResponse.LogContent content = taskLogRepository.findLatestRecord(taskId, entry.logType())
                    .map(record -> content(entry, record))
                    .orElseGet(() -> emptyContent(entry));
            logs.put(entry.type(), content);
        }
        return new TaskLogContentResponse(logs);
    }

    @Transactional
    public Optional<TaskLogResponse> append(UUID projectId, UUID taskId, TaskLogType logType, String content) {
        if (content == null || content.isEmpty()) {
            return Optional.empty();
        }
        String relativePath = taskId + "/" + logType.name().toLowerCase() + ".log";
        Path path = resolveLogPath(relativePath);
        byte[] bytes = content.getBytes(StandardCharsets.UTF_8);
        long previousLineCount = previousLineCount(taskId, logType, path);
        boolean hadContent = isNonEmptyFile(path);
        boolean previousEndsWithLineBreak = !hadContent || endsWithLineBreak(path);
        long lineCount = updatedLineCount(previousLineCount, previousEndsWithLineBreak, hadContent, content);
        try {
            Files.createDirectories(path.getParent());
            Files.write(path, bytes, StandardOpenOption.CREATE, StandardOpenOption.APPEND);
        } catch (IOException ex) {
            throw new TaskExecutionException(TaskErrorCode.LOG_WRITE_FAILED, "任务日志写入失败", ex);
        }
        String excerpt = TaskLogSanitizer.safeExcerpt(content);
        return Optional.of(taskLogRepository.create(
                projectId,
                taskId,
                logType,
                relativePath,
                bytes.length,
                lineCount,
                sha256(bytes),
                excerpt
        ));
    }

    @Transactional(readOnly = true)
    public DownloadableTaskLog download(UUID taskId, UUID logId) {
        TaskLogsRecord record = taskLogRepository.findForTask(taskId, logId)
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "TASK_LOG_NOT_FOUND", "任务日志不存在"));
        Path path = resolveLogPath(record.getFilePath());
        if (!Files.isRegularFile(path)) {
            throw new ApiException(HttpStatus.NOT_FOUND, "TASK_LOG_FILE_NOT_FOUND", "任务日志文件不存在");
        }
        try {
            Resource resource = new UrlResource(path.toUri());
            return new DownloadableTaskLog(resource, path.getFileName().toString(), record.getLogType());
        } catch (MalformedURLException ex) {
            throw new ApiException(HttpStatus.INTERNAL_SERVER_ERROR, "TASK_LOG_DOWNLOAD_FAILED", "任务日志无法下载");
        }
    }

    @Transactional(readOnly = true)
    public String readText(UUID taskId, UUID logId, long maxBytes) {
        if (logId == null) {
            return "";
        }
        TaskLogsRecord record = taskLogRepository.findForTask(taskId, logId)
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "TASK_LOG_NOT_FOUND", "任务日志不存在"));
        Path path = resolveLogPath(record.getFilePath());
        if (!Files.isRegularFile(path)) {
            return "";
        }
        try (var input = Files.newInputStream(path)) {
            byte[] bytes = input.readNBytes(maxBytes <= 0 ? 0 : Math.toIntExact(Math.min(maxBytes, Integer.MAX_VALUE)));
            return new String(bytes, StandardCharsets.UTF_8);
        } catch (IOException ex) {
            throw new ApiException(HttpStatus.INTERNAL_SERVER_ERROR, "TASK_LOG_READ_FAILED", "任务日志读取失败");
        }
    }

    @Transactional(readOnly = true)
    public String readTailText(UUID taskId, UUID logId, int lines) {
        if (logId == null || lines <= 0) {
            return "";
        }
        TaskLogsRecord record = taskLogRepository.findForTask(taskId, logId)
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "TASK_LOG_NOT_FOUND", "任务日志不存在"));
        Path path = resolveLogPath(record.getFilePath());
        if (!Files.isRegularFile(path)) {
            return "";
        }
        return TaskLogSanitizer.safeContent(TaskLogTailReader.read(path, 0, lines).content());
    }

    private TaskLogContentResponse.LogContent content(TaskLogContentRequest.Entry entry, TaskLogsRecord record) {
        Path path = resolveLogPath(record.getFilePath());
        if (!Files.isRegularFile(path)) {
            return new TaskLogContentResponse.LogContent(
                    entry.type(),
                    record.getId(),
                    entry.offset(),
                    entry.lines(),
                    0,
                    0,
                    false,
                    ""
            );
        }
        TaskLogTailReader.TailResult result = TaskLogTailReader.read(path, entry.offset(), entry.lines());
        long totalLines = record.getLineCount() == null ? TaskLogTailReader.countLines(path) : record.getLineCount();
        return new TaskLogContentResponse.LogContent(
                entry.type(),
                record.getId(),
                entry.offset(),
                entry.lines(),
                result.returnedLines(),
                totalLines,
                result.hasMore(),
                TaskLogSanitizer.safeContent(result.content())
        );
    }

    private TaskLogContentResponse.LogContent emptyContent(TaskLogContentRequest.Entry entry) {
        return new TaskLogContentResponse.LogContent(
                entry.type(),
                null,
                entry.offset(),
                entry.lines(),
                0,
                0,
                false,
                ""
        );
    }

    private long previousLineCount(UUID taskId, TaskLogType logType, Path path) {
        return taskLogRepository.findLatestRecord(taskId, logType)
                .map(TaskLogsRecord::getLineCount)
                .orElseGet(() -> TaskLogTailReader.countLines(path));
    }

    private long updatedLineCount(long previousLineCount, boolean previousEndsWithLineBreak, boolean hadContent, String content) {
        long appendedLines = TaskLogTailReader.countLines(content);
        if (appendedLines == 0) {
            return previousLineCount;
        }
        long result = previousLineCount + appendedLines;
        if (hadContent && !previousEndsWithLineBreak) {
            result--;
        }
        return Math.max(result, 0);
    }

    private boolean isNonEmptyFile(Path path) {
        try {
            return Files.isRegularFile(path) && Files.size(path) > 0;
        } catch (IOException ex) {
            throw new TaskExecutionException(TaskErrorCode.LOG_WRITE_FAILED, "任务日志状态读取失败", ex);
        }
    }

    private boolean endsWithLineBreak(Path path) {
        try (SeekableByteChannel channel = Files.newByteChannel(path, StandardOpenOption.READ)) {
            long size = channel.size();
            if (size == 0) {
                return true;
            }
            ByteBuffer buffer = ByteBuffer.allocate(1);
            channel.position(size - 1);
            channel.read(buffer);
            byte last = buffer.array()[0];
            return last == '\n' || last == '\r';
        } catch (IOException ex) {
            throw new TaskExecutionException(TaskErrorCode.LOG_WRITE_FAILED, "任务日志状态读取失败", ex);
        }
    }

    private Path resolveLogPath(String filePath) {
        Path raw = Path.of(filePath);
        Path resolved = raw.isAbsolute() ? raw.normalize() : logRoot.resolve(raw).normalize();
        if (!resolved.startsWith(logRoot)) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "TASK_LOG_PATH_INVALID", "任务日志路径非法");
        }
        return resolved;
    }

    private String sha256(byte[] bytes) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException(ex);
        }
    }

    public record DownloadableTaskLog(Resource resource, String filename, String logType) {
    }
}
