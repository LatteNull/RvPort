package cn.rvport.backend.kb.ai;

import cn.rvport.backend.task.TaskResponse;

public record KbAiExtensionCreateResponse(
        TaskResponse task,
        KbAiExtensionResponse run
) {
}
