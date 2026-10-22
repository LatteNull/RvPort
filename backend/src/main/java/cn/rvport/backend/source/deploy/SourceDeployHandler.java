package cn.rvport.backend.source.deploy;

import cn.rvport.backend.task.RvPortTaskTypes;
import cn.rvport.backend.worker.TaskExecutionContext;
import cn.rvport.backend.worker.TaskHandler;
import cn.rvport.backend.worker.TaskHandlerResult;
import org.springframework.stereotype.Component;

@Component
public class SourceDeployHandler implements TaskHandler {

    private final SourceDeployExecutor sourceDeployExecutor;

    public SourceDeployHandler(SourceDeployExecutor sourceDeployExecutor) {
        this.sourceDeployExecutor = sourceDeployExecutor;
    }

    @Override
    public String taskType() {
        return RvPortTaskTypes.SOURCE_DEPLOY;
    }

    @Override
    public TaskHandlerResult handle(TaskExecutionContext context) {
        SourceDeployTaskInput input = context.input(SourceDeployTaskInput.class);
        sourceDeployExecutor.deployExisting(input, context);
        context.progress(90, "源码部署完成");
        return TaskHandlerResult.success("源码部署成功");
    }
}
