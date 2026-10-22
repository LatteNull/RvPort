package cn.rvport.backend.analysis;

import static org.assertj.core.api.Assertions.assertThat;
import cn.rvport.backend.config.RvPortProperties;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class SpecializedAnalysisToolHealthServiceTests {

    @TempDir Path root;

    @Test
    void reportsAvailableWhenAllConfiguredExecutablesExist() throws Exception {
        Path python = executable("python");
        Path scanner = executable("scanner");
        Path clang = executable("clang");
        Path fpWorker = executable("fp-worker");
        Path moWorker = executable("mo-worker");
        Path sourceWorker = executable("source-worker");
        var service = service(true, python, scanner, clang, fpWorker, moWorker, sourceWorker);

        assertThat(service.health(SpecializedAnalyzerType.FLOATING_POINT).available()).isTrue();
        assertThat(service.health(SpecializedAnalyzerType.MEMORY_ORDER).available()).isTrue();
        assertThat(service.health(SpecializedAnalyzerType.FLOATING_POINT).commands()).containsKey("clang");
        assertThat(service.health(SpecializedAnalyzerType.FLOATING_POINT).versions()).containsKey("scanner");
    }

    @Test
    void reportsEveryMissingExecutableWithoutStartingExternalProcess() throws Exception {
        Path existing = executable("python");
        Path missing = root.resolve("missing");
        var service = service(true, existing, missing, missing, missing, missing, missing);

        assertThat(service.health(SpecializedAnalyzerType.FLOATING_POINT).available()).isFalse();
        assertThat(service.health(SpecializedAnalyzerType.FLOATING_POINT).reasons())
                .contains("scanner:NOT_EXECUTABLE", "clang:NOT_EXECUTABLE", "irWorker:NOT_EXECUTABLE");
        assertThat(service.health(SpecializedAnalyzerType.MEMORY_ORDER).reasons())
                .contains("irWorker:NOT_EXECUTABLE", "sourceWorker:NOT_EXECUTABLE");
    }

    @Test
    void reportsExistingDirectoryAsNonExecutableCommand() throws Exception {
        Path python = Files.createDirectory(root.resolve("python-directory"));
        var health = service(true, python, python, python, python, python, python)
                .health(SpecializedAnalyzerType.FLOATING_POINT);
        assertThat(health.available()).isFalse();
        assertThat(health.reasons()).contains("python:NOT_EXECUTABLE");
    }

    @Test
    void reportsRegularFileWithoutExecutePermission() throws Exception {
        Path nonExecutable = Files.writeString(root.resolve("non-executable"), "test");
        assertThat(nonExecutable.toFile().setExecutable(false, false)).isTrue();

        var health = service(true, nonExecutable, nonExecutable, nonExecutable,
                nonExecutable, nonExecutable, nonExecutable)
                .health(SpecializedAnalyzerType.FLOATING_POINT);

        assertThat(Files.isRegularFile(nonExecutable)).isTrue();
        assertThat(Files.isExecutable(nonExecutable)).isFalse();
        assertThat(health.reasons()).contains("python:NOT_EXECUTABLE");
    }

    @Test
    void disabledFeatureIsUnavailableEvenWithValidTools() throws Exception {
        Path executable = executable("tool");
        var health = service(false, executable, executable, executable, executable, executable, executable)
                .health(SpecializedAnalyzerType.FLOATING_POINT);

        assertThat(health.available()).isFalse();
        assertThat(health.status()).isEqualTo("UNAVAILABLE");
        assertThat(health.reasons()).contains("SPECIALIZED_ANALYSIS_DISABLED");
    }

    @Test
    void failedDoctorMakesAnalyzerUnavailableAndStartupRefreshesCache() throws Exception {
        Path executable = executable("tool");
        SpecializedAnalysisCommandProbe probe = mock(SpecializedAnalysisCommandProbe.class);
        when(probe.probe(any(List.class), any(Duration.class)))
                .thenReturn(new SpecializedAnalysisCommandProbe.ProbeResult(false, "bad", "EXIT_2"));
        var service = service(true, executable, executable, executable, executable, executable, executable, probe);

        assertThat(service.health(SpecializedAnalyzerType.MEMORY_ORDER).reasons()).contains("doctor:EXIT_2");
        service.inspectAtStartup();
        assertThat(service.health(SpecializedAnalyzerType.FLOATING_POINT).available()).isFalse();
    }

    private SpecializedAnalysisToolHealthService service(boolean enabled, Path python, Path scanner, Path clang,
            Path fpWorker, Path moWorker, Path sourceWorker) {
        SpecializedAnalysisCommandProbe probe = mock(SpecializedAnalysisCommandProbe.class);
        when(probe.probe(any(List.class), any(Duration.class)))
                .thenReturn(new SpecializedAnalysisCommandProbe.ProbeResult(true, "v1", null));
        return service(enabled, python, scanner, clang, fpWorker, moWorker, sourceWorker, probe);
    }

    private SpecializedAnalysisToolHealthService service(boolean enabled, Path python, Path scanner, Path clang,
            Path fpWorker, Path moWorker, Path sourceWorker, SpecializedAnalysisCommandProbe probe) {
        RvPortProperties.SpecializedAnalysis properties = new RvPortProperties.SpecializedAnalysis(
                enabled, root.toString(), 60, 1024L, 1024L, 1024L, 100,
                python.toString(), scanner.toString(), clang.toString(), fpWorker.toString(),
                python.toString(), moWorker.toString(), sourceWorker.toString());
        RvPortProperties rootProperties = new RvPortProperties(null, null, null, null, properties);
        return new SpecializedAnalysisToolHealthService(rootProperties, probe);
    }

    private Path executable(String name) throws Exception {
        Path path = Files.writeString(root.resolve(name), "test");
        path.toFile().setExecutable(true);
        return path;
    }
}
