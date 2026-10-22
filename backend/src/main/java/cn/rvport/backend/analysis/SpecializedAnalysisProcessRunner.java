package cn.rvport.backend.analysis;

import cn.rvport.backend.task.TaskLogType;
import cn.rvport.backend.worker.TaskCancelledException;
import cn.rvport.backend.worker.TaskExecutionContext;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import java.util.concurrent.TimeUnit;
import org.springframework.stereotype.Component;

@Component
public class SpecializedAnalysisProcessRunner {

    public ProcessResult run(List<String> command, Path workingDirectory, TaskExecutionContext context, Duration timeout) {
        Process process = null;
        StringBuilder captured = new StringBuilder();
        try {
            ProcessBuilder builder = new ProcessBuilder(command).directory(workingDirectory.toFile());
            builder.environment().put("PYTHONUTF8", "1");
            builder.environment().put("PYTHONIOENCODING", "utf-8");
            process = builder.start();
            context.registerLocalProcess(process, Duration.ofSeconds(10));
            Process active = process;
            Thread stdout = reader(active.getInputStream(), TaskLogType.STDOUT, context, captured);
            Thread stderr = reader(active.getErrorStream(), TaskLogType.STDERR, context, captured);
            if (!process.waitFor(timeout.toSeconds(), TimeUnit.SECONDS)) {
                process.destroy();
                if (!process.waitFor(10, TimeUnit.SECONDS)) process.destroyForcibly();
                throw new SpecializedAnalysisRuntimeException("专项分析执行超时");
            }
            stdout.join(Duration.ofSeconds(5));
            stderr.join(Duration.ofSeconds(5));
            return new ProcessResult(process.exitValue(), captured.toString());
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            if (process != null) process.destroyForcibly();
            throw new TaskCancelledException("专项分析已取消");
        } catch (IOException ex) {
            throw new SpecializedAnalysisRuntimeException("无法启动专项分析进程", ex);
        }
    }

    private Thread reader(java.io.InputStream stream, TaskLogType type, TaskExecutionContext context,
            StringBuilder captured) {
        return Thread.ofVirtual().start(() -> {
            try (BufferedReader lines = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8))) {
                String line;
                while ((line = lines.readLine()) != null) {
                    synchronized (captured) {
                        context.log(type, line);
                        context.log(TaskLogType.COMBINED, line);
                        if (captured.length() < 64 * 1024) captured.append(line).append('\n');
                    }
                }
            } catch (IOException ignored) {
                // 进程终止时流可能先关闭，退出码仍是最终判断依据。
            }
        });
    }

    public record ProcessResult(int exitCode, String output) { }
}
