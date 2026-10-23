package cn.rvport.backend.source.runtime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.credential.CredentialKind;
import cn.rvport.backend.credential.CredentialService;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

class ProcessGitClientAdapterTests {

    @Test
    void clonesBranchChecksOutCommitAndResolvesHead() throws Exception {
        List<List<String>> commands = new ArrayList<>();
        List<Map<String, String>> environments = new ArrayList<>();
        List<Process> processes = List.of(
                process(0, "clone ok", ""),
                process(0, "checkout ok", ""),
                process(0, "abc123\n", "")
        );
        AtomicReference<Integer> index = new AtomicReference<>(0);
        ProcessGitClientAdapter adapter = new ProcessGitClientAdapter((args, configurer) -> {
            commands.add(List.copyOf(args));
            Map<String, String> environment = new HashMap<>();
            configurer.configure(environment);
            environments.add(environment);
            return processes.get(index.getAndSet(index.get() + 1));
        });
        AtomicReference<Process> registered = new AtomicReference<>();
        Path worktree = Path.of("runtime", "secret-worktree").toAbsolutePath();

        GitSyncResult result = adapter.sync(new GitSyncCommand(
                "https://example.com/repository", "main", "release-1", worktree,
                null, Duration.ofSeconds(3), registered::set));

        assertThat(commands).containsExactly(
                List.of("git", "clone", "--no-tags", "--branch", "main", "https://example.com/repository", worktree.toString()),
                List.of("git", "-C", worktree.toString(), "checkout", "--detach", "release-1"),
                List.of("git", "-C", worktree.toString(), "rev-parse", "HEAD")
        );
        assertThat(environments).allSatisfy(environment ->
                assertThat(environment).containsEntry("GIT_TERMINAL_PROMPT", "0"));
        assertThat(registered.get()).isSameAs(processes.getLast());
        assertThat(result.exitCode()).isZero();
        assertThat(result.actualCommit()).isEqualTo("abc123");
        assertThat(result.stdout()).contains("clone ok", "checkout ok", "abc123").doesNotContain(worktree.toString());
        assertThat(result.duration()).isGreaterThanOrEqualTo(Duration.ZERO);
    }

    @Test
    void stopsAfterCloneFailureAndSanitizesCredentialAndWorktree() throws Exception {
        List<List<String>> commands = new ArrayList<>();
        Map<String, String> environment = new HashMap<>();
        String secret = "top-secret-token";
        Path worktree = Path.of("runtime", "private-worktree").toAbsolutePath();
        Process failedProcess = process(7, "failed " + worktree, "credential=" + secret);
        ProcessGitClientAdapter adapter = new ProcessGitClientAdapter((args, configurer) -> {
            commands.add(List.copyOf(args));
            configurer.configure(environment);
            return failedProcess;
        });
        CredentialService.GitRuntimeCredential credential = new CredentialService.GitRuntimeCredential(
                UUID.randomUUID(), CredentialKind.GIT_TOKEN, "", secret);

        GitSyncResult result = adapter.sync(new GitSyncCommand(
                "https://example.com/repository", "", "ignored", worktree,
                credential, Duration.ofSeconds(2), null));

        assertThat(commands).hasSize(1);
        assertThat(commands.getFirst()).doesNotContain("--branch");
        assertThat(environment)
                .containsEntry("GIT_TERMINAL_PROMPT", "0")
                .containsEntry("RVPORT_GIT_USERNAME", "oauth2")
                .containsEntry("RVPORT_GIT_PASSWORD", secret);
        assertThat(environment.get("GIT_ASKPASS")).isNotBlank();
        assertThat(result.exitCode()).isEqualTo(7);
        assertThat(result.actualCommit()).isEmpty();
        assertThat(result.stdout()).contains("<worktree>").doesNotContain(worktree.toString());
        assertThat(result.stderr()).contains("****").doesNotContain(secret);
    }

    @Test
    void returnsTimeoutResultAndDestroysProcess() throws Exception {
        Process process = process(0, "partial", "warning");
        when(process.waitFor(25, TimeUnit.MILLISECONDS)).thenReturn(false);
        ProcessGitClientAdapter adapter = new ProcessGitClientAdapter((args, configurer) -> process);

        GitSyncResult result = adapter.sync(new GitSyncCommand(
                "https://example.com/repository", null, null, Path.of("worktree"),
                null, Duration.ofMillis(25), null));

        assertThat(result.exitCode()).isEqualTo(124);
        assertThat(result.stdout()).contains("partial");
        assertThat(result.stderr()).contains("warning", "Git 命令执行超时");
        verify(process).destroyForcibly();
    }

    @Test
    void mapsStartAndInterruptFailuresWithoutUsingRealGit() throws Exception {
        ProcessGitClientAdapter startFailure = new ProcessGitClientAdapter((args, configurer) -> {
            throw new IOException("not installed");
        });
        GitSyncCommand command = new GitSyncCommand(
                "https://example.com/repository", null, null, Path.of("worktree"),
                null, Duration.ofSeconds(1), null);

        assertThatThrownBy(() -> startFailure.sync(command))
                .isInstanceOf(GitRuntimeException.class)
                .hasMessage("Git 命令启动失败")
                .hasCauseInstanceOf(IOException.class);

        Process interrupted = process(0, "", "");
        when(interrupted.waitFor(1_000, TimeUnit.MILLISECONDS)).thenThrow(new InterruptedException("stop"));
        ProcessGitClientAdapter interruptFailure = new ProcessGitClientAdapter((args, configurer) -> interrupted);
        try {
            assertThatThrownBy(() -> interruptFailure.sync(command))
                    .isInstanceOf(GitRuntimeException.class)
                    .hasMessage("Git 命令被中断")
                    .hasCauseInstanceOf(InterruptedException.class);
            assertThat(Thread.currentThread().isInterrupted()).isTrue();
        } finally {
            Thread.interrupted();
        }
    }

    @Test
    void stopsAfterCheckoutFailureAndAfterRevParseFailure() throws Exception {
        List<List<String>> commands = new ArrayList<>();
        List<Process> checkoutProcesses = List.of(
                process(0, "clone", ""), process(8, "", "checkout failed"));
        AtomicReference<Integer> checkoutIndex = new AtomicReference<>(0);
        ProcessGitClientAdapter checkoutAdapter = new ProcessGitClientAdapter((args, configurer) -> {
            commands.add(List.copyOf(args));
            return checkoutProcesses.get(checkoutIndex.getAndSet(checkoutIndex.get() + 1));
        });
        GitSyncCommand command = new GitSyncCommand(
                "https://example.com/repository", null, "bad-ref", Path.of("worktree"),
                null, null, null);

        GitSyncResult checkout = checkoutAdapter.sync(command);
        assertThat(checkout.exitCode()).isEqualTo(8);
        assertThat(checkout.actualCommit()).isEmpty();
        assertThat(commands).hasSize(2);

        List<Process> revProcesses = List.of(process(0, "clone", ""), process(9, "", "rev failed"));
        AtomicReference<Integer> revIndex = new AtomicReference<>(0);
        ProcessGitClientAdapter revAdapter = new ProcessGitClientAdapter(
                (args, configurer) -> revProcesses.get(revIndex.getAndSet(revIndex.get() + 1)));
        GitSyncResult revParse = revAdapter.sync(new GitSyncCommand(
                "https://example.com/repository", null, null, Path.of("worktree"), null, null, null));
        assertThat(revParse.exitCode()).isEqualTo(9);
        assertThat(revParse.actualCommit()).isEmpty();
        assertThat(revParse.stderr()).contains("rev failed");
    }

    @Test
    void blankCommitSkipsCheckoutButStillResolvesHead() throws Exception {
        List<List<String>> commands = new ArrayList<>();
        List<Process> processes = List.of(process(0, "clone", ""), process(0, "head\n", ""));
        AtomicReference<Integer> index = new AtomicReference<>(0);
        ProcessGitClientAdapter adapter = new ProcessGitClientAdapter((args, configurer) -> {
            commands.add(List.copyOf(args));
            return processes.get(index.getAndSet(index.get() + 1));
        });

        GitSyncResult result = adapter.sync(new GitSyncCommand(
                "https://example.com/repository", null, " ", Path.of("worktree"),
                null, Duration.ofSeconds(1), null));

        assertThat(commands).hasSize(2);
        assertThat(commands.get(1)).contains("rev-parse").doesNotContain("checkout");
        assertThat(result.actualCommit()).isEqualTo("head");
    }

    @Test
    void preparesExplicitCredentialAndHandlesSanitizationAndIoBoundaries() throws Exception {
        ProcessGitClientAdapter adapter = new ProcessGitClientAdapter((args, configurer) -> mock(Process.class));
        Map<String, String> environment = new HashMap<>();
        Path script = Files.createTempFile("askpass", ".cmd");
        CredentialService.GitRuntimeCredential credential = new CredentialService.GitRuntimeCredential(
                UUID.randomUUID(), CredentialKind.GIT_PASSWORD, "alice", "secret");

        ReflectionTestUtils.invokeMethod(adapter, "prepareEnvironment", environment, credential, script);
        assertThat(environment).containsEntry("RVPORT_GIT_USERNAME", "alice")
                .containsEntry("RVPORT_GIT_PASSWORD", "secret");

        GitSyncCommand command = new GitSyncCommand(
                "url", null, null, Path.of("worktree"),
                new CredentialService.GitRuntimeCredential(UUID.randomUUID(), CredentialKind.GIT_TOKEN, "bob", ""),
                Duration.ZERO, null);
        assertThat((String) ReflectionTestUtils.invokeMethod(adapter, "sanitize", null, command)).isEmpty();
        assertThat((String) ReflectionTestUtils.invokeMethod(adapter, "sanitize", "visible", command)).isEqualTo("visible");
        assertThat((String) ReflectionTestUtils.invokeMethod(adapter, "append", null, "next")).isEqualTo("next");
        assertThat((String) ReflectionTestUtils.invokeMethod(adapter, "append", " ", "next")).isEqualTo("next");
        assertThat((String) ReflectionTestUtils.invokeMethod(adapter, "append", "first", "next"))
                .isEqualTo("first" + System.lineSeparator() + "next");

        InputStream failing = new InputStream() {
            @Override
            public int read() throws IOException {
                throw new IOException("broken");
            }
        };
        assertThat((String) ReflectionTestUtils.invokeMethod(adapter, "readAll", failing)).isEmpty();
        ReflectionTestUtils.invokeMethod(adapter, "deleteQuietly", (Path) null);
        ReflectionTestUtils.invokeMethod(adapter, "deleteQuietly", script);
        assertThat(script).doesNotExist();
    }

    @Test
    void createsUnixAskPassScriptAndIgnoresNonEmptyDirectoryCleanupFailure() throws Exception {
        ProcessGitClientAdapter adapter = new ProcessGitClientAdapter((args, configurer) -> mock(Process.class));
        String original = System.getProperty("os.name");
        Path directory = Files.createTempDirectory("askpass-unix-test-");
        try {
            System.setProperty("os.name", "Linux");
            Path script = ReflectionTestUtils.invokeMethod(adapter, "createAskPassScript", directory);
            assertThat(script).hasFileName("askpass.sh");
            assertThat(Files.readString(script)).contains("#!/bin/sh", "RVPORT_GIT_PASSWORD");
            ReflectionTestUtils.invokeMethod(adapter, "deleteQuietly", directory);
            assertThat(directory).exists();
        } finally {
            if (original == null) {
                System.clearProperty("os.name");
            } else {
                System.setProperty("os.name", original);
            }
            try (var paths = Files.walk(directory)) {
                paths.sorted(java.util.Comparator.reverseOrder()).forEach(path -> {
                    try {
                        Files.deleteIfExists(path);
                    } catch (IOException ignored) {
                    }
                });
            }
        }
    }

    private Process process(int exitCode, String stdout, String stderr) throws Exception {
        Process process = mock(Process.class);
        when(process.getInputStream()).thenReturn(new ByteArrayInputStream(stdout.getBytes(StandardCharsets.UTF_8)));
        when(process.getErrorStream()).thenReturn(new ByteArrayInputStream(stderr.getBytes(StandardCharsets.UTF_8)));
        when(process.waitFor(org.mockito.ArgumentMatchers.anyLong(), org.mockito.ArgumentMatchers.eq(TimeUnit.MILLISECONDS)))
                .thenReturn(true);
        when(process.exitValue()).thenReturn(exitCode);
        when(process.destroyForcibly()).thenReturn(process);
        return process;
    }
}
