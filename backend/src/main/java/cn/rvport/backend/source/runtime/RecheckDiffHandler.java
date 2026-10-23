package cn.rvport.backend.source.runtime;

import cn.rvport.backend.source.RecheckTaskInput;
import cn.rvport.backend.task.RvPortTaskTypes;
import cn.rvport.backend.worker.TaskExecutionContext;
import cn.rvport.backend.worker.TaskHandler;
import cn.rvport.backend.worker.TaskHandlerResult;
import org.springframework.stereotype.Component;

@Component
public class RecheckDiffHandler implements TaskHandler {

    private final RecheckDiffRuntimeService runtimeService;

    public RecheckDiffHandler(RecheckDiffRuntimeService runtimeService) {
        this.runtimeService = runtimeService;
    }

    @Override
    public String taskType() {
        return RvPortTaskTypes.RECHECK_DIFF;
    }

    @Override
    public TaskHandlerResult handle(TaskExecutionContext context) {
        runtimeService.run(context.input(RecheckTaskInput.class), context);
        return TaskHandlerResult.success("复检差异生成完成");
    }
}
