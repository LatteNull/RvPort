package cn.rvport.backend.codexprovider;

import java.io.IOException;
import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import java.util.Map;

public interface CodexProcessRunner {
    CodexProcessResult run(
            List<String> command,
            Map<String, String> environment,
            String standardInput,
            Path workingDirectory,
            Duration timeout
    ) throws IOException, InterruptedException;
}
