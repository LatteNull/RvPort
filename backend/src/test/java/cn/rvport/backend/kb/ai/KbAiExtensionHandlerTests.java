package cn.rvport.backend.kb.ai;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.verify;

import cn.rvport.backend.task.RvPortTaskTypes;
import cn.rvport.backend.worker.TaskExecutionContext;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

class KbAiExtensionHandlerTests {

    @Test
    void exposesTaskTypeAndDelegatesContext() {
        KbAiExtensionService service = Mockito.mock(KbAiExtensionService.class);
        TaskExecutionContext context = Mockito.mock(TaskExecutionContext.class);
        KbAiExtensionHandler handler = new KbAiExtensionHandler(service);

        assertThat(handler.taskType()).isEqualTo(RvPortTaskTypes.KB_AI_EXTENSION);
        assertThat(handler.handle(context).message()).isEqualTo("知识库 AI 扩展完成");
        verify(service).execute(context);
    }

    @Test
    void propagatesServiceFailure() {
        KbAiExtensionService service = Mockito.mock(KbAiExtensionService.class);
        TaskExecutionContext context = Mockito.mock(TaskExecutionContext.class);
        RuntimeException failure = new RuntimeException("failed");
        org.mockito.Mockito.doThrow(failure).when(service).execute(context);

        assertThatThrownBy(() -> new KbAiExtensionHandler(service).handle(context)).isSameAs(failure);
    }
}
