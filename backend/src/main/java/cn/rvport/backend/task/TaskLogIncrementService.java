package cn.rvport.backend.task;

import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class TaskLogIncrementService {

    static final int MAX_RESPONSE_BYTES = 1024 * 1024;

    private final TaskLogEventRepository repository;

    public TaskLogIncrementService(TaskLogEventRepository repository) {
        this.repository = repository;
    }

    @Transactional(readOnly = true)
    public TaskLogIncrementResponse read(UUID taskId, TaskLogIncrementRequest request) {
        List<TaskLogEventView> candidates = repository.listAfter(taskId, request.afterEventId(), request.limit() + 1);
        StringBuilder merged = new StringBuilder();
        StringBuilder stdout = new StringBuilder();
        StringBuilder stderr = new StringBuilder();
        int mergedEvents = 0;
        int stdoutEvents = 0;
        int stderrEvents = 0;
        int responseBytes = 0;
        Long fromEventId = null;
        long latestEventId = request.afterEventId();
        int included = 0;

        for (TaskLogEventView event : candidates) {
            if (included >= request.limit()) {
                break;
            }
            String marker = event.logType() == TaskLogType.STDERR ? "[STDERR] " : "[STDOUT] ";
            int eventBytes = utf8Bytes(event.content()) * 2 + utf8Bytes(marker);
            if (included > 0 && responseBytes + eventBytes > MAX_RESPONSE_BYTES) {
                break;
            }
            if (fromEventId == null) {
                fromEventId = event.id();
            }
            merged.append(marker).append(event.content());
            mergedEvents++;
            if (event.logType() == TaskLogType.STDERR) {
                stderr.append(event.content());
                stderrEvents++;
            } else {
                stdout.append(event.content());
                stdoutEvents++;
            }
            responseBytes += eventBytes;
            latestEventId = event.id();
            included++;
        }

        Map<String, TaskLogIncrementResponse.LogIncrement> logs = new LinkedHashMap<>();
        logs.put("merged", new TaskLogIncrementResponse.LogIncrement(merged.toString(), mergedEvents));
        logs.put("stdout", new TaskLogIncrementResponse.LogIncrement(stdout.toString(), stdoutEvents));
        logs.put("stderr", new TaskLogIncrementResponse.LogIncrement(stderr.toString(), stderrEvents));
        return new TaskLogIncrementResponse(
                taskId,
                fromEventId,
                latestEventId,
                candidates.size() > included,
                logs
        );
    }

    private int utf8Bytes(String value) {
        return value.getBytes(StandardCharsets.UTF_8).length;
    }
}
