package cn.rvport.backend.analysis;

import cn.rvport.backend.config.RvPortProperties;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.time.Duration;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Service;

@Service
public class SpecializedAnalysisToolHealthService {

    private final RvPortProperties.SpecializedAnalysis properties;
    private final SpecializedAnalysisCommandProbe probe;
    private final Map<SpecializedAnalyzerType, ToolHealth> cache = new ConcurrentHashMap<>();

    public SpecializedAnalysisToolHealthService(RvPortProperties properties, SpecializedAnalysisCommandProbe probe) {
        this.properties = properties.specializedAnalysis();
        this.probe = probe;
    }

    public ToolHealth health(SpecializedAnalyzerType type) {
        return cache.computeIfAbsent(type, this::inspect);
    }

    @EventListener(ApplicationReadyEvent.class)
    public void inspectAtStartup() {
        cache.clear();
        health(SpecializedAnalyzerType.FLOATING_POINT);
        health(SpecializedAnalyzerType.MEMORY_ORDER);
    }

    private ToolHealth inspect(SpecializedAnalyzerType type) {
        List<String> missing = new ArrayList<>();
        Map<String, String> commands = new LinkedHashMap<>();
        Map<String, String> versions = new LinkedHashMap<>();
        if (!properties.enabled()) missing.add("SPECIALIZED_ANALYSIS_DISABLED");
        if (type == SpecializedAnalyzerType.FLOATING_POINT) {
            check("python", properties.floatingPython(), missing, commands);
            check("scanner", properties.floatingScanner(), missing, commands);
            check("clang", properties.floatingClang(), missing, commands);
            check("irWorker", properties.floatingIrWorker(), missing, commands);
        } else {
            check("python", properties.memoryOrderPython(), missing, commands);
            check("irWorker", properties.memoryOrderIrWorker(), missing, commands);
            check("sourceWorker", properties.memoryOrderSourceWorker(), missing, commands);
        }
        if (missing.isEmpty()) probe(type, missing, versions);
        return new ToolHealth(missing.isEmpty(), missing.isEmpty() ? "AVAILABLE" : "UNAVAILABLE", missing, commands,
                versions);
    }

    private void probe(SpecializedAnalyzerType type, List<String> missing, Map<String, String> versions) {
        if (type == SpecializedAnalyzerType.FLOATING_POINT) {
            probe("scanner", List.of(properties.floatingScanner(), "version"), missing, versions);
            probe("clang", List.of(properties.floatingClang(), "--version"), missing, versions);
            probe("irWorker", List.of(properties.floatingIrWorker(), "--version-json"), missing, versions);
        } else {
            probe("doctor", List.of(properties.memoryOrderPython(), "-m", "memory_order_analyzer", "doctor",
                    "--worker", properties.memoryOrderIrWorker()), missing, versions);
            probe("irWorker", List.of(properties.memoryOrderIrWorker(), "--protocol"), missing, versions);
            probe("sourceWorker", List.of(properties.memoryOrderSourceWorker(), "--source-analysis-protocol"),
                    missing, versions);
        }
    }

    private void probe(String name, List<String> command, List<String> missing, Map<String, String> versions) {
        SpecializedAnalysisCommandProbe.ProbeResult result = probe.probe(command, Duration.ofSeconds(20));
        if (!result.success()) missing.add(name + ":" + result.reason());
        else versions.put(name, result.output());
    }

    private void check(String name, String configuredPath, List<String> missing, Map<String, String> commands) {
        commands.put(name, configuredPath);
        try {
            Path path = Path.of(configuredPath).toAbsolutePath().normalize();
            if (!Files.isRegularFile(path) || !Files.isExecutable(path)) missing.add(name + ":NOT_EXECUTABLE");
        } catch (RuntimeException ex) {
            missing.add(name + ":INVALID_PATH");
        }
    }

    public record ToolHealth(boolean available, String status, List<String> reasons, Map<String, String> commands,
            Map<String, String> versions) {
        public ToolHealth(boolean available, String status, List<String> reasons, Map<String, String> commands) {
            this(available, status, reasons, commands, Map.of());
        }
    }
}
