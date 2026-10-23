package cn.rvport.backend.environment.runtime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.task.RvPortTaskTypes;
import cn.rvport.backend.worker.TaskExecutionContext;
import cn.rvport.backend.worker.TaskHandlerResult;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class EnvironmentRunScriptHandlerTests {

    private final SshRuntimeService service = mock(SshRuntimeService.class);
    private final EnvironmentRunScriptHandler handler = new EnvironmentRunScriptHandler(service);
    private final TaskExecutionContext context = mock(TaskExecutionContext.class);

    @Test
    void exposesTaskTypeAndDispatchesEnvironmentCheck() {
        EnvironmentTaskInput input = input("ENV_CHECK");
        when(context.input(EnvironmentTaskInput.class)).thenReturn(input);

        TaskHandlerResult result = handler.handle(context);

        assertThat(handler.taskType()).isEqualTo(RvPortTaskTypes.ENV_RUN_SCRIPT);
        assertThat(result.message()).isEqualTo("环境检查成功");
        verify(service).checkEnvironment(input, context);
    }

    @Test
    void dispatchesEnvironmentCollection() {
        EnvironmentTaskInput input = input("ENV_COLLECT");
        when(context.input(EnvironmentTaskInput.class)).thenReturn(input);

        TaskHandlerResult result = handler.handle(context);

        assertThat(result.message()).isEqualTo("环境采集任务完成");
        verify(service).collectEnvironment(input, context);
    }

    @Test
    void dispatchesCustomAndNullScriptTypesToScriptRunner() {
        for (String scriptType : new String[]{"CUSTOM_BASH", null}) {
            EnvironmentTaskInput input = input(scriptType);
            when(context.input(EnvironmentTaskInput.class)).thenReturn(input);

            TaskHandlerResult result = handler.handle(context);

            assertThat(result.message()).isEqualTo("远程脚本执行成功");
            verify(service).runScript(input, context);
        }
    }

    private EnvironmentTaskInput input(String scriptType) {
        return new EnvironmentTaskInput(
                UUID.randomUUID(), UUID.randomUUID(), null, 30, scriptType,
                null, null, null, null, null, null);
    }
}
