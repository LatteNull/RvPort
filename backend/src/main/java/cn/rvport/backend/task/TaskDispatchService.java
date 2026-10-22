package cn.rvport.backend.task;

import cn.rvport.backend.queue.TaskQueueClient;
import cn.rvport.backend.queue.TaskQueueMessage;
import java.time.OffsetDateTime;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class TaskDispatchService {

    private final TaskQueueClient taskQueueClient;
    private final TaskRepository taskRepository;
    private final TaskEventService taskEventService;

    public TaskDispatchService(
            TaskQueueClient taskQueueClient,
            TaskRepository taskRepository,
            TaskEventService taskEventService
    ) {
        this.taskQueueClient = taskQueueClient;
        this.taskRepository = taskRepository;
        this.taskEventService = taskEventService;
    }

    @Transactional
    public void publishAndMarkQueued(TaskView task) {
        taskQueueClient.publish(new TaskQueueMessage(task.id(), task.type(), task.projectId(), OffsetDateTime.now()));
        TaskView queued = taskRepository.markQueued(task.id());
        if (queued != null) {
            taskEventService.append(
                    queued.projectId(),
                    queued.id(),
                    TaskEventType.QUEUED,
                    TaskStatus.QUEUED,
                    queued.progress(),
                    "任务已投递队列"
            );
        }
    }

    @Transactional(readOnly = true)
    public TaskView requireTask(UUID taskId) {
        return taskRepository.findById(taskId)
                .orElseThrow(() -> new cn.rvport.backend.common.error.ApiException(
                        org.springframework.http.HttpStatus.NOT_FOUND,
                        "TASK_NOT_FOUND",
                        "任务不存在"
                ));
    }
}
