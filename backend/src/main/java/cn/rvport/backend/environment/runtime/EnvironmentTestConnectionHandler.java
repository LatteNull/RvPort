package cn.rvport.backend.environment.runtime;

import cn.rvport.backend.task.RvPortTaskTypes;
import cn.rvport.backend.worker.TaskExecutionContext;
import cn.rvport.backend.worker.TaskHandler;
import cn.rvport.backend.worker.TaskHandlerResult;
import org.springframework.stereotype.Component;

@Component
public class EnvironmentTestConnectionHandler implements TaskHandler {

    private final SshRuntimeService sshRuntimeService;

    public EnvironmentTestConnectionHandler(SshRuntimeService sshRuntimeService) {
        this.sshRuntimeService = sshRuntimeService;
    }

    @Override
    public String taskType() {
        return RvPortTaskTypes.ENV_TEST_CONNECTION;
    }

    @Override
    public TaskHandlerResult handle(TaskExecutionContext context) {
        EnvironmentTaskInput input = context.input(EnvironmentTaskInput.class);
        sshRuntimeService.testConnection(input, context);
        return TaskHandlerResult.success("环境连接测试成功");
    }
}
