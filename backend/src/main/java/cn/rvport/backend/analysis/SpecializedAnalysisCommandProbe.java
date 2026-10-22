package cn.rvport.backend.analysis;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.List;
import java.util.concurrent.TimeUnit;
import org.springframework.stereotype.Component;

@Component
public class SpecializedAnalysisCommandProbe {

    public ProbeResult probe(List<String> command, Duration timeout) {
        Process process = null;
        try {
            ProcessBuilder builder = new ProcessBuilder(command).redirectErrorStream(true);
            builder.environment().put("PYTHONUTF8", "1");
            builder.environment().put("PYTHONIOENCODING", "utf-8");
            process = builder.start();
            if (!process.waitFor(timeout.toSeconds(), TimeUnit.SECONDS)) {
                process.destroyForcibly();
                return new ProbeResult(false, "", "TIMEOUT");
            }
            byte[] bytes = process.getInputStream().readNBytes(16 * 1024);
            String output = new String(bytes, StandardCharsets.UTF_8).trim();
            return process.exitValue() == 0
                    ? new ProbeResult(true, output, null)
                    : new ProbeResult(false, output, "EXIT_" + process.exitValue());
        } catch (IOException ex) {
            return new ProbeResult(false, "", "START_FAILED");
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            if (process != null) process.destroyForcibly();
            return new ProbeResult(false, "", "INTERRUPTED");
        }
    }

    public record ProbeResult(boolean success, String output, String reason) {
    }
}
