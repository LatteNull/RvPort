package cn.rvport.backend.environment.runtime;

import cn.rvport.backend.task.RvPortTaskTypes;
import cn.rvport.backend.worker.TaskExecutionContext;
import cn.rvport.backend.worker.TaskHandler;
import cn.rvport.backend.worker.TaskHandlerResult;
import org.springframework.stereotype.Component;

@Component
public class EnvironmentCollectHandler implements TaskHandler {

    private final SshRuntimeService sshRuntimeService;

    public EnvironmentCollectHandler(SshRuntimeService sshRuntimeService) {
        this.sshRuntimeService = sshRuntimeService;
    }

    @Override
    public String taskType() {
        return RvPortTaskTypes.ENV_COLLECT;
    }

    @Override
    public TaskHandlerResult handle(TaskExecutionContext context) {
        EnvironmentTaskInput input = context.input(EnvironmentTaskInput.class);
        sshRuntimeService.collectEnvironment(input, context);
        return TaskHandlerResult.success("环境采集任务完成");
    }
}
