package cn.rvport.backend.project;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.environment.EnvironmentRepository;
import cn.rvport.backend.environment.EnvironmentView;
import cn.rvport.backend.source.SourceRepository;
import cn.rvport.backend.source.SourceRevisionView;
import cn.rvport.backend.task.TaskLogRepository;
import cn.rvport.backend.task.TaskRepository;
import cn.rvport.backend.task.TaskView;
import java.util.Objects;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ProjectAccessService {

    private final ProjectRepository projectRepository;
    private final TaskRepository taskRepository;
    private final EnvironmentRepository environmentRepository;
    private final SourceRepository sourceRepository;
    private final TaskLogRepository taskLogRepository;

    public ProjectAccessService(
            ProjectRepository projectRepository,
            TaskRepository taskRepository,
            EnvironmentRepository environmentRepository,
            SourceRepository sourceRepository,
            TaskLogRepository taskLogRepository
    ) {
        this.projectRepository = projectRepository;
        this.taskRepository = taskRepository;
        this.environmentRepository = environmentRepository;
        this.sourceRepository = sourceRepository;
        this.taskLogRepository = taskLogRepository;
    }

    @Transactional(readOnly = true)
    public ProjectView requireProjectAccess(UUID projectId, UUID actorUserId, boolean superAdmin) {
        ProjectView project = projectRepository.findById(projectId)
                .orElseThrow(() -> notFound("PROJECT_NOT_FOUND", "项目不存在"));
        if (!superAdmin && !Objects.equals(project.createdBy(), actorUserId)) {
            throw notFound("PROJECT_NOT_FOUND", "项目不存在");
        }
        return project;
    }

    @Transactional(readOnly = true)
    public TaskView requireTaskAccess(UUID taskId, UUID actorUserId, boolean superAdmin) {
        TaskView task = taskRepository.findById(taskId)
                .orElseThrow(() -> notFound("TASK_NOT_FOUND", "任务不存在"));
        requireProjectAccess(task.projectId(), actorUserId, superAdmin);
        return task;
    }

    @Transactional(readOnly = true)
    public EnvironmentView requireEnvironmentAccess(UUID environmentId, UUID actorUserId, boolean superAdmin) {
        EnvironmentView environment = environmentRepository.findById(environmentId)
                .orElseThrow(() -> notFound("ENVIRONMENT_NOT_FOUND", "环境不存在"));
        requireProjectAccess(environment.projectId(), actorUserId, superAdmin);
        return environment;
    }

    @Transactional(readOnly = true)
    public SourceRevisionView requireSourceRevisionAccess(UUID projectId, UUID sourceRevisionId, UUID actorUserId, boolean superAdmin) {
        requireProjectAccess(projectId, actorUserId, superAdmin);
        SourceRevisionView revision = sourceRepository.findById(sourceRevisionId)
                .orElseThrow(() -> notFound("SOURCE_REVISION_NOT_FOUND", "源码版本不存在"));
        if (!Objects.equals(revision.projectId(), projectId)) {
            throw notFound("SOURCE_REVISION_NOT_FOUND", "源码版本不存在");
        }
        return revision;
    }

    @Transactional(readOnly = true)
    public void requireTaskLogAccess(UUID taskId, UUID logId, UUID actorUserId, boolean superAdmin) {
        requireTaskAccess(taskId, actorUserId, superAdmin);
        if (taskLogRepository.findForTask(taskId, logId).isEmpty()) {
            throw notFound("TASK_LOG_NOT_FOUND", "任务日志不存在");
        }
    }

    private ApiException notFound(String code, String message) {
        return new ApiException(HttpStatus.NOT_FOUND, code, message);
    }
}
