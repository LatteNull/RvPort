package cn.rvport.backend.codexprovider;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;

class DefaultCodexProcessRunnerTests {

    @Test
    void capturesStdoutStderrAndMergedOutput() throws Exception {
        DefaultCodexProcessRunner runner = new DefaultCodexProcessRunner();
        var workDir = Files.createTempDirectory("rvport-process-runner-test-");
        CodexProcessResult result = runner.run(command("basic"), Map.of(), null, workDir, Duration.ofSeconds(5));

        assertThat(result.exitCode()).isZero();
        assertThat(result.timedOut()).isFalse();
        assertThat(result.stdout()).contains("out");
        assertThat(result.stderr()).contains("err");
        assertThat(result.mergedOutput()).contains("[STDOUT]");
        assertThat(result.mergedOutput()).contains("[STDERR]");
    }

    @Test
    void writesUtf8StdinAndPreservesUnicodeOutput() throws Exception {
        DefaultCodexProcessRunner runner = new DefaultCodexProcessRunner();
        Path workDir = Files.createTempDirectory("rvport-process-runner-unicode-");
        String input = "中文提示词与边界字符 \uD83D\uDE80";

        CodexProcessResult result = runner.run(command("echo"), Map.of(), input, workDir, Duration.ofSeconds(5));

        assertThat(result.exitCode()).isZero();
        assertThat(result.stdout()).isEqualTo(input);
        assertThat(result.stderr()).isEqualTo("错误流：" + input);
        assertThat(result.mergedOutput()).contains(input, "错误流：").doesNotContain("\uFFFD");
    }

    @Test
    void stopsAtCompleteUtf8CharacterWhenOutputLimitIsReached() throws Exception {
        DefaultCodexProcessRunner runner = new DefaultCodexProcessRunner();
        Path workDir = Files.createTempDirectory("rvport-process-runner-limit-");

        CodexProcessResult result = runner.run(command("limit"), Map.of(), "", workDir, Duration.ofSeconds(5));

        assertThat(result.exitCode()).isZero();
        assertThat(result.stdout()).hasSize(65_535).matches("a{65535}").doesNotContain("中", "\uFFFD");
        assertThat(result.stdout().getBytes(StandardCharsets.UTF_8)).hasSize(65_535);
    }

    @Test
    void reportsTimeoutAndStdinFailureWithoutEchoingInput() throws Exception {
        DefaultCodexProcessRunner runner = new DefaultCodexProcessRunner();
        Path workDir = Files.createTempDirectory("rvport-process-runner-failure-");

        CodexProcessResult timeout = runner.run(command("sleep"), Map.of(), "机密提示词", workDir, Duration.ofMillis(50));
        assertThat(timeout.timedOut()).isTrue();
        assertThat(timeout.exitCode()).isEqualTo(-1);

        String largeSecret = "机密".repeat(4_000_000);
        CodexProcessResult failed = runner.run(command("exit"), Map.of(), largeSecret, workDir, Duration.ofSeconds(5));
        assertThat(failed.exitCode()).isEqualTo(-1);
        assertThat(failed.stderr()).contains("Agent stdin write failed").doesNotContain("机密");
        assertThat(failed.mergedOutput()).doesNotContain("机密");
    }

    @Test
    void writesStdinEvenWhenCommonPoolHasOnlyTwoWorkers() throws Exception {
        List<String> command = command("small-pool");
        command.add(1, "-Djava.util.concurrent.ForkJoinPool.common.parallelism=2");
        Process process = new ProcessBuilder(command).redirectErrorStream(true).start();
        try {
            assertThat(process.waitFor(15, TimeUnit.SECONDS)).isTrue();
            String output = new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
            assertThat(process.exitValue()).as(output).isZero();
            assertThat(output).contains("small-pool-ok");
        } finally {
            process.destroyForcibly();
        }
    }

    private static List<String> command(String mode) {
        List<String> command = new ArrayList<>();
        command.add(Path.of(System.getProperty("java.home"), "bin", isWindows() ? "java.exe" : "java").toString());
        command.add("-cp");
        command.add(System.getProperty("java.class.path"));
        command.add(ProcessFixture.class.getName());
        command.add(mode);
        return command;
    }

    private static boolean isWindows() {
        return System.getProperty("os.name", "").toLowerCase().contains("win");
    }

    public static final class ProcessFixture {
        private ProcessFixture() {
        }

        public static void main(String[] args) throws Exception {
            switch (args[0]) {
                case "basic" -> {
                    System.out.println("out");
                    System.err.println("err");
                }
                case "echo" -> {
                    byte[] input = System.in.readAllBytes();
                    System.out.write(input);
                    System.err.write("错误流：".getBytes(StandardCharsets.UTF_8));
                    System.err.write(input);
                }
                case "limit" -> {
                    System.out.write("a".repeat(65_535).getBytes(StandardCharsets.UTF_8));
                    System.out.write("中".getBytes(StandardCharsets.UTF_8));
                }
                case "sleep" -> Thread.sleep(5_000);
                case "small-pool" -> {
                    var result = new DefaultCodexProcessRunner().run(command("echo"), Map.of(), "管道输入",
                            Path.of(System.getProperty("java.io.tmpdir")), Duration.ofSeconds(5));
                    if (result.timedOut() || result.exitCode() != 0 || !result.stdout().equals("管道输入")
                            || !result.stderr().equals("错误流：管道输入")) {
                        throw new AssertionError(result);
                    }
                    System.out.println("small-pool-ok");
                }
                case "exit" -> System.exit(0);
                default -> throw new IllegalArgumentException("unknown mode");
            }
        }
    }
}
