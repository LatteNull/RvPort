package cn.rvport.backend.worker;

import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.Duration;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class LocalProcessCancellableResourceTests {

    @Mock
    private Process process;

    @Mock
    private ProcessHandle handle;

    @Mock
    private ProcessHandle child;

    @Test
    void destroysProcessTreeDuringCancel() throws Exception {
        when(process.toHandle()).thenReturn(handle);
        when(handle.descendants()).thenReturn(Stream.of(child));
        when(process.waitFor(10L, java.util.concurrent.TimeUnit.MILLISECONDS)).thenReturn(true);
        when(handle.isAlive()).thenReturn(false);

        new LocalProcessCancellableResource(process, Duration.ofMillis(10)).cancel();

        verify(child).destroy();
        verify(handle).destroy();
    }

    @Test
    void forciblyDestroysProcessTreeAfterGracePeriod() throws Exception {
        when(process.toHandle()).thenReturn(handle);
        when(handle.descendants()).thenReturn(Stream.of(child), Stream.of(child));
        when(process.waitFor(1L, java.util.concurrent.TimeUnit.MILLISECONDS)).thenReturn(false);
        when(handle.isAlive()).thenReturn(true);

        new LocalProcessCancellableResource(process, Duration.ofMillis(1)).cancel();

        verify(child).destroy();
        verify(handle).destroy();
        verify(child).destroyForcibly();
        verify(handle).destroyForcibly();
    }

    @Test
    void restoresInterruptFlagWhenWaitIsInterrupted() throws Exception {
        when(process.toHandle()).thenReturn(handle);
        when(handle.descendants()).thenReturn(Stream.empty());
        when(process.waitFor(1L, java.util.concurrent.TimeUnit.MILLISECONDS)).thenThrow(new InterruptedException("stop"));
        when(handle.isAlive()).thenReturn(false);

        try {
            new LocalProcessCancellableResource(process, Duration.ofMillis(1)).cancel();
            org.assertj.core.api.Assertions.assertThat(Thread.currentThread().isInterrupted()).isTrue();
        } finally {
            Thread.interrupted();
        }
    }
}
