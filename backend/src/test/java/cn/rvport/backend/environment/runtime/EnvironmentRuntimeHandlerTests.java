package cn.rvport.backend.environment.runtime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.environment.EnvironmentRepository;
import cn.rvport.backend.task.RvPortTaskTypes;
import cn.rvport.backend.task.TaskErrorCode;
import cn.rvport.backend.task.TaskExecutionException;
import cn.rvport.backend.worker.TaskExecutionContext;
import cn.rvport.backend.worker.TaskHandlerResult;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class EnvironmentRuntimeHandlerTests {

    @Mock
    private SshRuntimeService sshRuntimeService;

    @Mock
    private EnvironmentRepository environmentRepository;

    @Mock
    private TaskExecutionContext context;

    @Test
    void testConnectionHandlerDelegatesToSshRuntime() {
        EnvironmentTaskInput input = input();
        when(context.input(EnvironmentTaskInput.class)).thenReturn(input);
        EnvironmentTestConnectionHandler handler = new EnvironmentTestConnectionHandler(sshRuntimeService);

        TaskHandlerResult result = handler.handle(context);

        assertThat(handler.taskType()).isEqualTo(RvPortTaskTypes.ENV_TEST_CONNECTION);
        assertThat(result.message()).isEqualTo("环境连接测试成功");
        verify(sshRuntimeService).testConnection(input, context);
    }

    @Test
    void envCheckScriptHandlerUsesConnectionProbe() {
        EnvironmentTaskInput input = new EnvironmentTaskInput(
                UUID.randomUUID(),
                UUID.randomUUID(),
                null,
                60,
                "ENV_CHECK",
                java.util.List.of("CONNECTION"),
                null,
                null,
                null,
                null,
                null
        );
        when(context.input(EnvironmentTaskInput.class)).thenReturn(input);
        EnvironmentRunScriptHandler handler = new EnvironmentRunScriptHandler(sshRuntimeService);

        TaskHandlerResult result = handler.handle(context);

        verify(sshRuntimeService).checkEnvironment(input, context);
        assertThat(result.message()).isEqualTo("环境检查成功");
    }

    @Test
    void scriptHandlerDelegatesBuiltinScript() {
        EnvironmentTaskInput input = new EnvironmentTaskInput(
                UUID.randomUUID(),
                UUID.randomUUID(),
                null,
                60,
                "BUILTIN_SCRIPT",
                null,
                null,
                null,
                java.util.Map.of("name", "PRINT_WORKDIR"),
                null,
                null
        );
        when(context.input(EnvironmentTaskInput.class)).thenReturn(input);
        EnvironmentRunScriptHandler handler = new EnvironmentRunScriptHandler(sshRuntimeService);

        TaskHandlerResult result = handler.handle(context);

        verify(sshRuntimeService).runScript(input, context);
        assertThat(result.message()).isEqualTo("远程脚本执行成功");
    }

    @Test
    void collectHandlerUpdatesLastCollectedAfterSuccessfulProbe() {
        EnvironmentTaskInput input = input();
        when(context.input(EnvironmentTaskInput.class)).thenReturn(input);
        EnvironmentCollectHandler handler = new EnvironmentCollectHandler(sshRuntimeService);

        TaskHandlerResult result = handler.handle(context);

        assertThat(handler.taskType()).isEqualTo(RvPortTaskTypes.ENV_COLLECT);
        assertThat(result.message()).isEqualTo("环境采集任务完成");
        verify(sshRuntimeService).collectEnvironment(input, context);
    }

    private EnvironmentTaskInput input() {
        return new EnvironmentTaskInput(UUID.randomUUID(), UUID.randomUUID(), null, 30);
    }
}
