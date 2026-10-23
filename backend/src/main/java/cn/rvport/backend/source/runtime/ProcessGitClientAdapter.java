package cn.rvport.backend.source.runtime;

import cn.rvport.backend.credential.CredentialKind;
import cn.rvport.backend.credential.CredentialService;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import org.springframework.stereotype.Component;

@Component
public class ProcessGitClientAdapter implements GitClientAdapter {

    private static final Duration DEFAULT_TIMEOUT = Duration.ofMinutes(5);
    private final ProcessStarter processStarter;

    public ProcessGitClientAdapter() {
        this(ProcessGitClientAdapter::startProcess);
    }

    ProcessGitClientAdapter(ProcessStarter processStarter) {
        this.processStarter = processStarter;
    }

    @Override
    public GitSyncResult sync(GitSyncCommand command) {
        Instant startedAt = Instant.now();
        Path askPassDir = null;
        Path askPassScript = null;
        try {
            CredentialService.GitRuntimeCredential credential = command.credential();
            if (credential != null) {
                askPassDir = Files.createTempDirectory("rvport-git-askpass-");
                askPassScript = createAskPassScript(askPassDir);
            }
            List<String> stdout = new ArrayList<>();
            List<String> stderr = new ArrayList<>();
            int exitCode = runClone(command, askPassScript, stdout, stderr);
            if (exitCode == 0 && command.gitCommit() != null && !command.gitCommit().isBlank()) {
                exitCode = run(List.of("git", "-C", command.worktreeDir().toString(), "checkout", "--detach", command.gitCommit()),
                        command, askPassScript, stdout, stderr);
            }
            String actualCommit = "";
            if (exitCode == 0) {
                ProcessResult revParse = runProcess(List.of("git", "-C", command.worktreeDir().toString(), "rev-parse", "HEAD"),
                        command, askPassScript);
                stdout.add(revParse.stdout());
                stderr.add(revParse.stderr());
                exitCode = revParse.exitCode();
                if (exitCode == 0) {
                    actualCommit = revParse.stdout().trim();
                }
            }
            return new GitSyncResult(
                    exitCode,
                    sanitize(String.join(System.lineSeparator(), stdout), command),
                    sanitize(String.join(System.lineSeparator(), stderr), command),
                    actualCommit,
                    Duration.between(startedAt, Instant.now())
            );
        } catch (IOException ex) {
            throw new GitRuntimeException("Git 执行准备失败", ex);
        } finally {
            deleteQuietly(askPassScript);
            deleteQuietly(askPassDir);
        }
    }

    private int runClone(GitSyncCommand command, Path askPassScript, List<String> stdout, List<String> stderr) {
        List<String> args = new ArrayList<>();
        args.add("git");
        args.add("clone");
        args.add("--no-tags");
        if (command.gitBranch() != null && !command.gitBranch().isBlank()) {
            args.add("--branch");
            args.add(command.gitBranch());
        }
        args.add(command.gitUrl());
        args.add(command.worktreeDir().toString());
        return run(args, command, askPassScript, stdout, stderr);
    }

    private int run(List<String> args, GitSyncCommand command, Path askPassScript, List<String> stdout, List<String> stderr) {
        ProcessResult result = runProcess(args, command, askPassScript);
        stdout.add(result.stdout());
        stderr.add(result.stderr());
        return result.exitCode();
    }

    private ProcessResult runProcess(List<String> args, GitSyncCommand command, Path askPassScript) {
        try {
            Process process = processStarter.start(args, environment ->
                    prepareEnvironment(environment, command.credential(), askPassScript));
            if (command.processRegistrar() != null) {
                command.processRegistrar().accept(process);
            }
            CompletableFuture<String> stdoutFuture = CompletableFuture.supplyAsync(() -> readAll(process.getInputStream()));
            CompletableFuture<String> stderrFuture = CompletableFuture.supplyAsync(() -> readAll(process.getErrorStream()));
            boolean finished = process.waitFor(timeout(command).toMillis(), TimeUnit.MILLISECONDS);
            if (!finished) {
                process.destroyForcibly();
                return new ProcessResult(124, stdoutFuture.join(), append(stderrFuture.join(), "Git 命令执行超时"));
            }
            return new ProcessResult(process.exitValue(), stdoutFuture.join(), stderrFuture.join());
        } catch (IOException ex) {
            throw new GitRuntimeException("Git 命令启动失败", ex);
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new GitRuntimeException("Git 命令被中断", ex);
        }
    }

    private void prepareEnvironment(Map<String, String> environment, CredentialService.GitRuntimeCredential credential, Path askPassScript) {
        environment.put("GIT_TERMINAL_PROMPT", "0");
        if (credential == null) {
            return;
        }
        String username = credential.username() == null || credential.username().isBlank() ? "oauth2" : credential.username();
        if (credential.kind() == CredentialKind.GIT_TOKEN && (credential.username() == null || credential.username().isBlank())) {
            username = "oauth2";
        }
        environment.put("GIT_ASKPASS", askPassScript.toString());
        environment.put("RVPORT_GIT_USERNAME", username);
        environment.put("RVPORT_GIT_PASSWORD", credential.secret());
    }

    private Path createAskPassScript(Path directory) throws IOException {
        boolean windows = System.getProperty("os.name", "").toLowerCase().contains("win");
        Path script = directory.resolve(windows ? "askpass.cmd" : "askpass.sh");
        String content = windows ? windowsAskPass() : unixAskPass();
        Files.writeString(script, content, StandardCharsets.UTF_8);
        if (!windows) {
            script.toFile().setExecutable(true, true);
        }
        return script;
    }

    private String windowsAskPass() {
        return "@echo off\r\n"
                + "echo %* | findstr /I \"Username\" >nul\r\n"
                + "if %errorlevel%==0 (\r\n"
                + "  echo %RVPORT_GIT_USERNAME%\r\n"
                + ") else (\r\n"
                + "  echo %RVPORT_GIT_PASSWORD%\r\n"
                + ")\r\n";
    }

    private String unixAskPass() {
        return "#!/bin/sh\n"
                + "case \"$1\" in\n"
                + "  *Username*) printf '%s\\n' \"$RVPORT_GIT_USERNAME\" ;;\n"
                + "  *) printf '%s\\n' \"$RVPORT_GIT_PASSWORD\" ;;\n"
                + "esac\n";
    }

    private Duration timeout(GitSyncCommand command) {
        return command.timeout() == null ? DEFAULT_TIMEOUT : command.timeout();
    }

    private String sanitize(String value, GitSyncCommand command) {
        if (value == null) {
            return "";
        }
        String sanitized = value;
        CredentialService.GitRuntimeCredential credential = command.credential();
        if (credential != null && credential.secret() != null && !credential.secret().isBlank()) {
            sanitized = sanitized.replace(credential.secret(), "****");
        }
        if (command.worktreeDir() != null) {
            sanitized = sanitized
                    .replace(command.worktreeDir().toString(), "<worktree>")
                    .replace(command.worktreeDir().toAbsolutePath().normalize().toString(), "<worktree>");
        }
        return sanitized;
    }

    private String readAll(InputStream inputStream) {
        try (inputStream) {
            return new String(inputStream.readAllBytes(), StandardCharsets.UTF_8);
        } catch (IOException ex) {
            return "";
        }
    }

    private String append(String current, String next) {
        if (current == null || current.isBlank()) {
            return next;
        }
        return current + System.lineSeparator() + next;
    }

    private void deleteQuietly(Path path) {
        if (path == null) {
            return;
        }
        try {
            Files.deleteIfExists(path);
        } catch (IOException ignored) {
            // 临时凭据文件删除失败不应覆盖 Git 执行结果。
        }
    }

    private static Process startProcess(List<String> args, EnvironmentConfigurer environmentConfigurer) throws IOException {
        ProcessBuilder builder = new ProcessBuilder(args);
        builder.redirectErrorStream(false);
        environmentConfigurer.configure(builder.environment());
        return builder.start();
    }

    @FunctionalInterface
    interface ProcessStarter {
        Process start(List<String> args, EnvironmentConfigurer environmentConfigurer) throws IOException;
    }

    @FunctionalInterface
    interface EnvironmentConfigurer {
        void configure(Map<String, String> environment);
    }

    private record ProcessResult(int exitCode, String stdout, String stderr) {
    }
}
