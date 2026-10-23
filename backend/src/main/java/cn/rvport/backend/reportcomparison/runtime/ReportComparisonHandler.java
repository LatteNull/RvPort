package cn.rvport.backend.reportcomparison.runtime;

import cn.rvport.backend.reportcomparison.ReportComparisonTaskInput;
import cn.rvport.backend.task.RvPortTaskTypes;
import cn.rvport.backend.worker.TaskExecutionContext;
import cn.rvport.backend.worker.TaskHandler;
import cn.rvport.backend.worker.TaskHandlerResult;
import org.springframework.stereotype.Component;

@Component
public class ReportComparisonHandler implements TaskHandler {

    private final ReportComparisonRuntimeService runtimeService;

    public ReportComparisonHandler(ReportComparisonRuntimeService runtimeService) {
        this.runtimeService = runtimeService;
    }

    @Override
    public String taskType() {
        return RvPortTaskTypes.REPORT_COMPARE;
    }

    @Override
    public TaskHandlerResult handle(TaskExecutionContext context) {
        runtimeService.run(context.input(ReportComparisonTaskInput.class), context);
        return TaskHandlerResult.success("报告对比完成");
    }
}
