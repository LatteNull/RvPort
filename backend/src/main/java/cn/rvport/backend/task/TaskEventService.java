package cn.rvport.backend.task;

import java.util.List;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

@Service
public class TaskEventService {

    private final TaskEventRepository taskEventRepository;
    private final TaskSseBroker taskSseBroker;
    private final TaskSseEventBroadcaster taskSseEventBroadcaster;

    public TaskEventService(
            TaskEventRepository taskEventRepository,
            TaskSseBroker taskSseBroker,
            TaskSseEventBroadcaster taskSseEventBroadcaster
    ) {
        this.taskEventRepository = taskEventRepository;
        this.taskSseBroker = taskSseBroker;
        this.taskSseEventBroadcaster = taskSseEventBroadcaster;
    }

    public TaskEventView append(
            UUID projectId,
            UUID taskId,
            TaskEventType eventType,
            TaskStatus status,
            Integer progress,
            String message
    ) {
        return append(projectId, taskId, eventType, status, progress, message, null, null);
    }

    public TaskEventView append(
            UUID projectId,
            UUID taskId,
            TaskEventType eventType,
            TaskStatus status,
            Integer progress,
            String message,
            String logLevel,
            String logExcerpt
    ) {
        TaskEventView event = taskEventRepository.append(projectId, taskId, eventType, status, progress, message, logLevel, logExcerpt);
        publishAfterCommit(event);
        return event;
    }

    public TaskEventView appendProjectContextChanged(
            UUID projectId,
            String stageId,
            TaskEventResource resource,
            List<String> changedFields,
            String message
    ) {
        TaskEventView event = taskEventRepository.appendProjectContextChanged(projectId, stageId, resource, changedFields, message);
        publishAfterCommit(event);
        return event;
    }

    public List<TaskEventView> listAfter(UUID projectId, long lastEventId, int limit) {
        return taskEventRepository.listAfter(projectId, lastEventId, limit);
    }

    public long latestEventId(UUID projectId) {
        return taskEventRepository.latestId(projectId);
    }

    private void publishAfterCommit(TaskEventView event) {
        if (!TransactionSynchronizationManager.isSynchronizationActive()) {
            taskSseBroker.publish(event);
            taskSseEventBroadcaster.publishTaskEvent(event);
            return;
        }
        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCommit() {
                taskSseBroker.publish(event);
                taskSseEventBroadcaster.publishTaskEvent(event);
            }
        });
    }
}
