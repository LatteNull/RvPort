package cn.rvport.backend.analysis;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import org.junit.jupiter.api.Test;

class SpecializedAnalysisCommandProbeTests {

    private final SpecializedAnalysisCommandProbe probe = new SpecializedAnalysisCommandProbe();

    @Test
    void reportsSuccessNonZeroTimeoutAndMissingCommand() {
        assertThat(probe.probe(javaCommand("output"), Duration.ofSeconds(10)))
                .satisfies(result -> {
                    assertThat(result.success()).isTrue();
                    assertThat(result.output()).contains("probe-ok");
                });
        assertThat(probe.probe(javaCommand("exit"), Duration.ofSeconds(10)).reason()).isEqualTo("EXIT_4");
        assertThat(probe.probe(javaCommand("sleep"), Duration.ZERO).reason()).isEqualTo("TIMEOUT");
        assertThat(probe.probe(List.of("definitely-missing-specialized-tool"), Duration.ofSeconds(1)).reason())
                .isEqualTo("START_FAILED");
    }

    @Test
    void interruptionIsReportedAndFlagIsRestored() {
        Thread.currentThread().interrupt();
        try {
            assertThat(probe.probe(javaCommand("sleep"), Duration.ofSeconds(10)).reason()).isEqualTo("INTERRUPTED");
            assertThat(Thread.currentThread().isInterrupted()).isTrue();
        } finally {
            Thread.interrupted();
        }
    }

    private List<String> javaCommand(String mode) {
        Path executable = Path.of(System.getProperty("java.home"), "bin",
                System.getProperty("os.name").startsWith("Windows") ? "java.exe" : "java");
        return List.of(executable.toString(), "-cp", System.getProperty("java.class.path"), Fixture.class.getName(), mode);
    }

    public static final class Fixture {
        public static void main(String[] args) throws Exception {
            switch (args[0]) {
                case "output" -> System.out.println("probe-ok");
                case "exit" -> System.exit(4);
                case "sleep" -> Thread.sleep(30_000);
                default -> throw new IllegalArgumentException(args[0]);
            }
        }
    }
}
