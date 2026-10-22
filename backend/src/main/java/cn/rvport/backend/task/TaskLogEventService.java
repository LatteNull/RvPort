package cn.rvport.backend.task;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

@Service
public class TaskLogEventService {

    private static final int MAX_CHUNK_LENGTH = 4000;

    private final TaskLogEventRepository repository;
    private final TaskLogSseBroker sseBroker;
    private final TaskSseEventBroadcaster taskSseEventBroadcaster;

    public TaskLogEventService(
            TaskLogEventRepository repository,
            TaskLogSseBroker sseBroker,
            TaskSseEventBroadcaster taskSseEventBroadcaster
    ) {
        this.repository = repository;
        this.sseBroker = sseBroker;
        this.taskSseEventBroadcaster = taskSseEventBroadcaster;
    }

    public List<TaskLogEventView> append(UUID projectId, UUID taskId, TaskLogType logType, String content) {
        if (content == null || content.isEmpty()) {
            return List.of();
        }
        List<TaskLogEventView> events = repository.append(projectId, taskId, logType, chunks(TaskLogSanitizer.safeContent(content)));
        publishAfterCommit(events);
        return events;
    }

    public List<TaskLogEventView> listAfter(UUID taskId, long lastEventId, int limit) {
        return repository.listAfter(taskId, lastEventId, Math.min(Math.max(limit, 1), 1000));
    }

    public long count(UUID taskId) {
        return repository.count(taskId);
    }

    private List<String> chunks(String content) {
        List<String> chunks = new ArrayList<>();
        int offset = 0;
        while (offset < content.length()) {
            int end = Math.min(offset + MAX_CHUNK_LENGTH, content.length());
            chunks.add(content.substring(offset, end));
            offset = end;
        }
        return chunks;
    }

    private void publishAfterCommit(List<TaskLogEventView> events) {
        if (events.isEmpty()) {
            return;
        }
        if (!TransactionSynchronizationManager.isSynchronizationActive()) {
            events.forEach(this::publish);
            return;
        }
        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCommit() {
                events.forEach(TaskLogEventService.this::publish);
            }
        });
    }

    private void publish(TaskLogEventView event) {
        sseBroker.publish(event);
        taskSseEventBroadcaster.publishTaskLogEvent(event);
    }
}
