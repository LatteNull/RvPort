package cn.rvport.backend.source.runtime;

import cn.rvport.backend.task.RvPortTaskTypes;
import cn.rvport.backend.worker.TaskExecutionContext;
import cn.rvport.backend.worker.TaskHandler;
import cn.rvport.backend.worker.TaskHandlerResult;
import org.springframework.stereotype.Component;

@Component
public class SourceGitSyncHandler implements TaskHandler {

    private final SourceFetchRuntimeService sourceFetchRuntimeService;

    public SourceGitSyncHandler(SourceFetchRuntimeService sourceFetchRuntimeService) {
        this.sourceFetchRuntimeService = sourceFetchRuntimeService;
    }

    @Override
    public String taskType() {
        return RvPortTaskTypes.SOURCE_GIT_SYNC;
    }

    @Override
    public TaskHandlerResult handle(TaskExecutionContext context) {
        SourceGitSyncInput input = context.input(SourceGitSyncInput.class);
        sourceFetchRuntimeService.sync(input, context);
        return TaskHandlerResult.success("Git 源码同步成功");
    }
}
