package cn.rvport.backend.kb.ai;

import cn.rvport.backend.task.RvPortTaskTypes;
import cn.rvport.backend.worker.TaskExecutionContext;
import cn.rvport.backend.worker.TaskHandler;
import cn.rvport.backend.worker.TaskHandlerResult;
import org.springframework.stereotype.Component;

@Component
public class KbAiExtensionHandler implements TaskHandler {

    private final KbAiExtensionService service;

    public KbAiExtensionHandler(KbAiExtensionService service) {
        this.service = service;
    }

    @Override
    public String taskType() {
        return RvPortTaskTypes.KB_AI_EXTENSION;
    }

    @Override
    public TaskHandlerResult handle(TaskExecutionContext context) {
        service.execute(context);
        return TaskHandlerResult.success("知识库 AI 扩展完成");
    }
}
