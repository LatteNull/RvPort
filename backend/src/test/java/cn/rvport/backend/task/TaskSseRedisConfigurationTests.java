package cn.rvport.backend.task;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.config.RvPortAppMode;
import cn.rvport.backend.config.TaskSseBroadcastProperties;
import cn.rvport.backend.config.WorkerProperties;
import org.springframework.context.ApplicationListener;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.data.redis.listener.RedisMessageListenerContainer;
import org.junit.jupiter.api.Test;

class TaskSseRedisConfigurationTests {

    private final TaskSseRedisConfiguration configuration = new TaskSseRedisConfiguration();

    @Test
    void apiCapableModesSubscribeToRedisBroadcasts() {
        assertThat(configuration.subscribes(RvPortAppMode.API)).isTrue();
        assertThat(configuration.subscribes(RvPortAppMode.COMBINED)).isTrue();
    }

    @Test
    void workerOnlyModeDoesNotSubscribeToRedisBroadcasts() {
        assertThat(configuration.subscribes(RvPortAppMode.WORKER)).isFalse();
        assertThat(configuration.subscribes(null)).isFalse();
    }

    @Test
    void starterSkipsDisabledWorkerOnlyAndAlreadyRunningContainers() {
        RedisMessageListenerContainer container = mock(RedisMessageListenerContainer.class);

        starter(container, false, RvPortAppMode.API).onApplicationEvent(null);
        starter(container, true, RvPortAppMode.WORKER).onApplicationEvent(null);
        when(container.isRunning()).thenReturn(true);
        starter(container, true, RvPortAppMode.API).onApplicationEvent(null);

        verify(container, never()).start();
    }

    @Test
    void starterStartsEligibleContainerAndContainsStartupFailure() {
        RedisMessageListenerContainer container = mock(RedisMessageListenerContainer.class);
        when(container.isRunning()).thenReturn(false);
        starter(container, true, RvPortAppMode.COMBINED).onApplicationEvent(null);
        verify(container).start();

        RedisMessageListenerContainer failing = mock(RedisMessageListenerContainer.class);
        when(failing.isRunning()).thenReturn(false);
        doThrow(new IllegalStateException("redis unavailable")).when(failing).start();
        starter(failing, true, RvPortAppMode.API).onApplicationEvent(null);
        verify(failing).start();
    }

    private ApplicationListener<ApplicationReadyEvent> starter(
            RedisMessageListenerContainer container,
            boolean enabled,
            RvPortAppMode mode
    ) {
        return configuration.taskSseRedisMessageListenerStarter(
                container,
                new TaskSseBroadcastProperties(enabled, "rvport", "tasks", "logs"),
                new WorkerProperties(true, "worker", mode, 1, 4, 10, 60));
    }
}
