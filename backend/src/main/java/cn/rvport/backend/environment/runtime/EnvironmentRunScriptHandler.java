package cn.rvport.backend.environment.runtime;

import cn.rvport.backend.task.RvPortTaskTypes;
import cn.rvport.backend.worker.TaskExecutionContext;
import cn.rvport.backend.worker.TaskHandler;
import cn.rvport.backend.worker.TaskHandlerResult;
import org.springframework.stereotype.Component;

@Component
public class EnvironmentRunScriptHandler implements TaskHandler {

    private final SshRuntimeService sshRuntimeService;

    public EnvironmentRunScriptHandler(SshRuntimeService sshRuntimeService) {
        this.sshRuntimeService = sshRuntimeService;
    }

    @Override
    public String taskType() {
        return RvPortTaskTypes.ENV_RUN_SCRIPT;
    }

    @Override
    public TaskHandlerResult handle(TaskExecutionContext context) {
        EnvironmentTaskInput input = context.input(EnvironmentTaskInput.class);
        if ("ENV_CHECK".equals(input.scriptType())) {
            sshRuntimeService.checkEnvironment(input, context);
            return TaskHandlerResult.success("环境检查成功");
        }
        if ("ENV_COLLECT".equals(input.scriptType())) {
            sshRuntimeService.collectEnvironment(input, context);
            return TaskHandlerResult.success("环境采集任务完成");
        }
        sshRuntimeService.runScript(input, context);
        return TaskHandlerResult.success("远程脚本执行成功");
    }
}
