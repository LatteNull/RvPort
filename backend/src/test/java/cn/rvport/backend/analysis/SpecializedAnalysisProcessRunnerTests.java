package cn.rvport.backend.analysis;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.atLeastOnce;
import static org.mockito.Mockito.verify;

import cn.rvport.backend.task.TaskLogType;
import cn.rvport.backend.worker.TaskCancelledException;
import cn.rvport.backend.worker.TaskExecutionContext;
import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class SpecializedAnalysisProcessRunnerTests {

    @TempDir Path tempDir;
    private final SpecializedAnalysisProcessRunner runner = new SpecializedAnalysisProcessRunner();

    @Test
    void capturesUtf8OutputAndExitCode() {
        TaskExecutionContext context = mock(TaskExecutionContext.class);
        var result = runner.run(javaCommand("output"), tempDir, context, Duration.ofSeconds(10));

        assertThat(result.exitCode()).isEqualTo(0);
        assertThat(result.output()).contains("中文输出");
        verify(context).registerLocalProcess(any(Process.class), any(Duration.class));
        verify(context).log(TaskLogType.STDOUT, "中文输出");
        verify(context).log(TaskLogType.COMBINED, "中文输出");
    }

    @Test
    void preservesNonZeroExitCode() {
        TaskExecutionContext context = mock(TaskExecutionContext.class);
        var result = runner.run(javaCommand("exit"), tempDir, context, Duration.ofSeconds(10));
        assertThat(result.exitCode()).isEqualTo(3);
        verify(context).log(TaskLogType.STDERR, "failure");
        verify(context).log(TaskLogType.COMBINED, "failure");
    }

    @Test
    void capsCapturedDiagnosticOutputButContinuesStreamingLogs() {
        TaskExecutionContext context = mock(TaskExecutionContext.class);
        var result = runner.run(javaCommand("large"), tempDir, context, Duration.ofSeconds(10));

        assertThat(result.exitCode()).isZero();
        assertThat(result.output().length()).isLessThan(67_000);
        verify(context, atLeastOnce()).log(TaskLogType.STDOUT, "x".repeat(1_000));
    }

    @Test
    void reportsTimeoutAndLaunchFailure() {
        assertThatThrownBy(() -> runner.run(javaCommand("sleep"), tempDir, mock(TaskExecutionContext.class),
                Duration.ZERO)).isInstanceOf(SpecializedAnalysisRuntimeException.class).hasMessageContaining("超时");
        assertThatThrownBy(() -> runner.run(List.of(tempDir.resolve("missing-command").toString()), tempDir,
                mock(TaskExecutionContext.class), Duration.ofSeconds(1)))
                .isInstanceOf(SpecializedAnalysisRuntimeException.class).hasMessageContaining("无法启动");
    }

    @Test
    void mapsInterruptionToCancellationAndRestoresFlag() {
        Thread.currentThread().interrupt();
        try {
            assertThatThrownBy(() -> runner.run(javaCommand("sleep"), tempDir, mock(TaskExecutionContext.class),
                    Duration.ofSeconds(10))).isInstanceOf(TaskCancelledException.class);
            assertThat(Thread.currentThread().isInterrupted()).isTrue();
        } finally {
            Thread.interrupted();
        }
    }

    private List<String> javaCommand(String mode) {
        Path executable = Path.of(System.getProperty("java.home"), "bin",
                System.getProperty("os.name").startsWith("Windows") ? "java.exe" : "java");
        return List.of(executable.toString(), "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8",
                "-cp", System.getProperty("java.class.path"), Fixture.class.getName(), mode);
    }

    public static final class Fixture {
        public static void main(String[] args) throws Exception {
            switch (args[0]) {
                case "output" -> System.out.println("中文输出");
                case "exit" -> { System.err.println("failure"); System.exit(3); }
                case "sleep" -> Thread.sleep(30_000);
                case "large" -> {
                    for (int i = 0; i < 100; i++) System.out.println("x".repeat(1_000));
                }
                default -> throw new IllegalArgumentException(args[0]);
            }
        }
    }
}
