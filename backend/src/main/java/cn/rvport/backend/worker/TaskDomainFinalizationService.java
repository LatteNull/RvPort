package cn.rvport.backend.worker;

import cn.rvport.backend.task.TaskEventService;
import cn.rvport.backend.task.TaskRepository;
import cn.rvport.backend.task.TaskView;
import cn.rvport.backend.task.TaskStatus;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import java.util.List;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class TaskDomainFinalizationService {
    private static final Logger log = LoggerFactory.getLogger(TaskDomainFinalizationService.class);
    private final TaskDomainFinalizationRepository repository;
    private final TaskRepository tasks;
    private final TaskEventService events;

    public TaskDomainFinalizationService(TaskDomainFinalizationRepository repository, TaskRepository tasks, TaskEventService events) {
        this.repository = repository;
        this.tasks = tasks;
        this.events = events;
    }

    @Transactional
    public int reconcile(UUID taskId) {
        TaskView task = tasks.lockById(taskId);
        if (task != null && task.status() == TaskStatus.SUCCEEDED) {
            log.warn("Successful task has unfinished domain records; manual audit required taskId={}", taskId);
            return 0;
        }
        return task == null ? 0 : finish(task);
    }

    @Transactional
    public int finish(TaskView task) {
        int updated = repository.finish(task);
        if (updated > 0) {
            events.appendProjectContextChanged(task.projectId(), task.stageId(), task.resource(),
                    List.of("status", "finishedAt"), "任务关联运行状态已收敛");
        }
        return updated;
    }
}
