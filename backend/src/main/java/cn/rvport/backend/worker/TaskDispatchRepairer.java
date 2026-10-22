package cn.rvport.backend.worker;

import cn.rvport.backend.task.TaskDispatchService;
import cn.rvport.backend.task.TaskRepository;
import cn.rvport.backend.task.TaskView;
import java.time.OffsetDateTime;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(prefix = "rvport.worker", name = "enabled", havingValue = "true")
public class TaskDispatchRepairer {

    private static final Logger log = LoggerFactory.getLogger(TaskDispatchRepairer.class);

    private final TaskRepository taskRepository;
    private final TaskDispatchService taskDispatchService;

    public TaskDispatchRepairer(TaskRepository taskRepository, TaskDispatchService taskDispatchService) {
        this.taskRepository = taskRepository;
        this.taskDispatchService = taskDispatchService;
    }

    @Scheduled(fixedDelayString = "${rvport.worker.pending-dispatch-repair-interval-ms:30000}")
    public void repairPendingDispatch() {
        OffsetDateTime before = OffsetDateTime.now().minusSeconds(10);
        for (TaskView task : taskRepository.findPendingBefore(before, 50)) {
            try {
                taskDispatchService.publishAndMarkQueued(task);
            } catch (RuntimeException ex) {
                log.warn("Failed to repair pending task dispatch taskId={}", task.id(), ex);
            }
        }
    }
}
