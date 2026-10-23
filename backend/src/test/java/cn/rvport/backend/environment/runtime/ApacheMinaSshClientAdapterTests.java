package cn.rvport.backend.environment.runtime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.credential.CredentialKind;
import cn.rvport.backend.task.TaskErrorCode;
import cn.rvport.backend.task.TaskLogType;
import cn.rvport.backend.worker.TaskExecutionContext;
import java.io.ByteArrayOutputStream;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.time.Duration;
import java.util.EnumSet;
import java.util.HexFormat;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicReference;
import org.apache.sshd.client.SshClient;
import org.apache.sshd.client.channel.ClientChannel;
import org.apache.sshd.client.channel.ClientChannelEvent;
import org.apache.sshd.client.channel.ChannelExec;
import org.apache.sshd.client.future.AuthFuture;
import org.apache.sshd.client.future.ConnectFuture;
import org.apache.sshd.client.future.OpenFuture;
import org.apache.sshd.client.session.ClientSession;
import org.apache.sshd.sftp.client.SftpClient;
import org.mockito.ArgumentCaptor;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.test.util.ReflectionTestUtils;

class ApacheMinaSshClientAdapterTests {

    @TempDir
    Path tempDir;

    @Test
    void executesPasswordCommandAndMapsOutputWithoutNetwork() throws Exception {
        SshFixture fixture = fixture("RVPORT_REMOTE_PID=41\nRVPORT_REMOTE_PGID=42\nhello\n", "warning\n",
                EnumSet.of(ClientChannelEvent.CLOSED), 0);
        ApacheMinaSshClientAdapter adapter = adapter(fixture);
        TaskExecutionContext context = mock(TaskExecutionContext.class);
        SshCommandRequest request = new SshCommandRequest(
                target(CredentialKind.SSH_PASSWORD), null, "printf hello", null, false,
                Duration.ofSeconds(2), Duration.ofSeconds(3), context);

        SshCommandResult result = adapter.execute(request);

        assertThat(result.exitCode()).isZero();
        assertThat(result.stdout()).isEqualTo("hello");
        assertThat(result.stderr()).isEqualTo("warning\n");
        assertThat(result.duration()).isGreaterThanOrEqualTo(Duration.ZERO);
        verify(fixture.session).addPasswordIdentity("password");
        verify(context).registerRemoteProcess(request.target().environmentId(), 41L, 42L, "rvport-ssh-command");
        assertThat(fixture.command.get()).contains("printf hello");
    }

    @Test
    void streamsStdinAndOutputThroughExecutionContext() throws Exception {
        SshFixture fixture = fixture("line one\n", "line two\n", EnumSet.of(ClientChannelEvent.CLOSED), null);
        ByteArrayOutputStream stdin = new ByteArrayOutputStream();
        when(fixture.channel.getInvertedIn()).thenReturn(stdin);
        ApacheMinaSshClientAdapter adapter = adapter(fixture);
        TaskExecutionContext context = mock(TaskExecutionContext.class);
        SshCommandRequest request = new SshCommandRequest(
                target(CredentialKind.SSH_PASSWORD), null, "cat", "中文输入", true,
                Duration.ofSeconds(2), Duration.ofSeconds(3), context);

        SshCommandResult result = adapter.execute(request);

        assertThat(stdin.toString(StandardCharsets.UTF_8)).isEqualTo("中文输入");
        assertThat(result.exitCode()).isEqualTo(-1);
        assertThat(result.stdout()).isEmpty();
        assertThat(result.stderr()).isEmpty();
        verify(context).log(TaskLogType.STDOUT, "line one" + System.lineSeparator());
        verify(context).log(org.mockito.ArgumentMatchers.eq(TaskLogType.STDERR),
                org.mockito.ArgumentMatchers.argThat(value -> value.trim().equals("line two")));
    }

    @Test
    void mapsCommandTimeoutAndInvalidCredential() throws Exception {
        SshFixture timeout = fixture("", "", EnumSet.noneOf(ClientChannelEvent.class), 0);
        ApacheMinaSshClientAdapter timeoutAdapter = adapter(timeout);

        assertThatThrownBy(() -> timeoutAdapter.execute(new SshCommandRequest(
                target(CredentialKind.SSH_PASSWORD), null, "sleep", Duration.ofSeconds(1), Duration.ofMillis(10))))
                .isInstanceOfSatisfying(SshRuntimeException.class, ex -> {
                    assertThat(ex.getCause()).isNull();
                    assertThat(ex.errorCode()).isEqualTo(TaskErrorCode.REMOTE_COMMAND_FAILED);
                    assertThat(ex).hasMessage("SSH 命令执行超时");
                });

        SshFixture invalid = fixture("", "", EnumSet.of(ClientChannelEvent.CLOSED), 0);
        ApacheMinaSshClientAdapter invalidAdapter = adapter(invalid);
        assertThatThrownBy(() -> invalidAdapter.execute(new SshCommandRequest(
                target(CredentialKind.GIT_TOKEN), null, "true", Duration.ofSeconds(1), Duration.ofSeconds(1))))
                .isInstanceOfSatisfying(SshRuntimeException.class, ex ->
                        assertThat(ex.errorCode()).isEqualTo(TaskErrorCode.CREDENTIAL_INVALID));
    }

    @Test
    void classifiesAuthenticationAndGeneralConnectionFailures() throws Exception {
        SshClient authClient = mock(SshClient.class);
        when(authClient.connect(anyString(), anyString(), org.mockito.ArgumentMatchers.anyInt()))
                .thenThrow(new IllegalStateException("Permission denied"));
        ApacheMinaSshClientAdapter authAdapter = new ApacheMinaSshClientAdapter(() -> authClient);

        assertThatThrownBy(() -> authAdapter.execute(new SshCommandRequest(
                target(CredentialKind.SSH_PASSWORD), null, "true", Duration.ofSeconds(1), Duration.ofSeconds(1))))
                .isInstanceOfSatisfying(SshRuntimeException.class, ex ->
                        assertThat(ex.errorCode()).isEqualTo(TaskErrorCode.CREDENTIAL_INVALID));

        SshClient failedClient = mock(SshClient.class);
        when(failedClient.connect(anyString(), anyString(), org.mockito.ArgumentMatchers.anyInt()))
                .thenThrow(new IllegalStateException("network unavailable"));
        ApacheMinaSshClientAdapter failedAdapter = new ApacheMinaSshClientAdapter(() -> failedClient);
        assertThatThrownBy(() -> failedAdapter.execute(new SshCommandRequest(
                target(CredentialKind.SSH_PASSWORD), null, "true", Duration.ofSeconds(1), Duration.ofSeconds(1))))
                .isInstanceOfSatisfying(SshRuntimeException.class, ex ->
                        assertThat(ex.errorCode()).isEqualTo(TaskErrorCode.HANDLER_FAILED));
    }

    @Test
    void wrappedCommandDoesNotInterpretPrintfFormatSpecifiers() throws Exception {
        ApacheMinaSshClientAdapter adapter = new ApacheMinaSshClientAdapter();
        Method method = ApacheMinaSshClientAdapter.class.getDeclaredMethod("wrappedCommand", String.class, boolean.class);
        method.setAccessible(true);

        String wrapped = (String) method.invoke(adapter, "printf 'value=%s\\n' \"ok\"", false);

        assertThat(wrapped)
                .contains("value=%s")
                .contains("\"ok\"")
                .contains("RVPORT_REMOTE_PID=%s")
                .startsWith("sh -lc ");
    }

    @Test
    void wrappedCommandRunsInForegroundWhenCommandRequiresStdin() throws Exception {
        ApacheMinaSshClientAdapter adapter = new ApacheMinaSshClientAdapter();
        Method method = ApacheMinaSshClientAdapter.class.getDeclaredMethod("wrappedCommand", String.class, boolean.class);
        method.setAccessible(true);

        String wrapped = (String) method.invoke(adapter, "cat > \"$tmp\"; bash \"$tmp\"", true);

        assertThat(wrapped)
                .contains("pid=$$")
                .contains("( cat >")
                .doesNotContain("&\npid=$!");
    }

    @Test
    void loggingOutputStreamKeepsUserOutputWhenRuntimePidLinesShareChunk() throws Exception {
        TaskExecutionContext context = org.mockito.Mockito.mock(TaskExecutionContext.class);
        Class<?> streamClass = Class.forName("cn.rvport.backend.environment.runtime.ApacheMinaSshClientAdapter$LoggingOutputStream");
        Constructor<?> constructor = streamClass.getDeclaredConstructor(
                ByteArrayOutputStream.class,
                TaskExecutionContext.class,
                TaskLogType.class,
                boolean.class,
                Object.class
        );
        constructor.setAccessible(true);
        Object stream = constructor.newInstance(new ByteArrayOutputStream(), context, TaskLogType.STDOUT, true, new Object());
        Method write = streamClass.getDeclaredMethod("write", byte[].class, int.class, int.class);
        Method flush = streamClass.getDeclaredMethod("flushRemainder");
        write.setAccessible(true);
        flush.setAccessible(true);
        byte[] bytes = """
                RVPORT_REMOTE_PID=123
                RVPORT_REMOTE_PGID=123
                RVPORT_REAL_CUSTOM_BASH_START
                uname_m=riscv64
                """.getBytes(StandardCharsets.UTF_8);

        write.invoke(stream, bytes, 0, bytes.length);
        flush.invoke(stream);

        ArgumentCaptor<String> contentCaptor = ArgumentCaptor.forClass(String.class);
        org.mockito.Mockito.verify(context, org.mockito.Mockito.times(2)).log(
                org.mockito.Mockito.eq(TaskLogType.STDOUT),
                contentCaptor.capture()
        );
        String combined = String.join("", contentCaptor.getAllValues());
        assertThat(combined)
                .contains("RVPORT_REAL_CUSTOM_BASH_START")
                .contains("uname_m=riscv64")
                .doesNotContain("RVPORT_REMOTE_PID")
                .doesNotContain("RVPORT_REMOTE_PGID");
        org.mockito.Mockito.verify(context, org.mockito.Mockito.atLeastOnce()).log(
                org.mockito.Mockito.eq(TaskLogType.COMBINED),
                org.mockito.Mockito.contains("[STDOUT]")
        );
    }

    @Test
    void utilityMethodsHandleNullEscapingRuntimeMarkersAndAllStdinForms() {
        ApacheMinaSshClientAdapter adapter = new ApacheMinaSshClientAdapter();

        assertThat((Long) ReflectionTestUtils.invokeMethod(adapter, "firstLong",
                java.util.regex.Pattern.compile("ID=(\\d+)"), "ID=42")).isEqualTo(42L);
        assertThat((Long) ReflectionTestUtils.invokeMethod(adapter, "firstLong",
                java.util.regex.Pattern.compile("ID=(\\d+)"), null)).isNull();
        assertThat((String) ReflectionTestUtils.invokeMethod(adapter, "stripRvportRuntimeLines",
                "RVPORT_REMOTE_PID=1\nvisible\nRVPORT_REMOTE_PGID=2\n")).isEqualTo("visible");
        assertThat((String) ReflectionTestUtils.invokeMethod(adapter, "stripRvportRuntimeLines", (String) null))
                .isEmpty();
        assertThat((String) ReflectionTestUtils.invokeMethod(adapter, "shellQuote", "a'b"))
                .isEqualTo("'a'\"'\"'b'");

        SshCommandRequest noInput = new SshCommandRequest(
                target(CredentialKind.SSH_PASSWORD), null, null, null, false,
                Duration.ofSeconds(1), Duration.ofSeconds(1), null);
        SshCommandRequest textInput = new SshCommandRequest(
                target(CredentialKind.SSH_PASSWORD), null, "cat", "", false,
                Duration.ofSeconds(1), Duration.ofSeconds(1), null);
        SshCommandRequest streamInput = new SshCommandRequest(
                target(CredentialKind.SSH_PASSWORD), null, "cat", null,
                new ByteArrayInputStream("stream".getBytes(StandardCharsets.UTF_8)), false,
                Duration.ofSeconds(1), Duration.ofSeconds(1), null);
        assertThat((boolean) ReflectionTestUtils.invokeMethod(adapter, "hasStdin", noInput)).isFalse();
        assertThat((boolean) ReflectionTestUtils.invokeMethod(adapter, "hasStdin", textInput)).isTrue();
        assertThat((boolean) ReflectionTestUtils.invokeMethod(adapter, "hasStdin", streamInput)).isTrue();

        ByteArrayOutputStream textTarget = new ByteArrayOutputStream();
        ReflectionTestUtils.invokeMethod(adapter, "writeStdin", textInput, textTarget);
        assertThat(textTarget.toString(StandardCharsets.UTF_8)).isEmpty();
        ByteArrayOutputStream streamTarget = new ByteArrayOutputStream();
        ReflectionTestUtils.invokeMethod(adapter, "writeStdin", streamInput, streamTarget);
        assertThat(streamTarget.toString(StandardCharsets.UTF_8)).isEqualTo("stream");
    }

    @Test
    void classifiesCredentialIndicatorsAcrossNestedCauses() {
        ApacheMinaSshClientAdapter adapter = new ApacheMinaSshClientAdapter();

        for (String indicator : new String[]{"auth", "credential", "keypair", "private key",
                "bad password", "permission denied"}) {
            Exception failure = new IllegalStateException("outer", new IOException(indicator));
            assertThat((String) ReflectionTestUtils.invokeMethod(adapter, "classify", failure))
                    .isEqualTo(TaskErrorCode.CREDENTIAL_INVALID);
        }
        assertThat((String) ReflectionTestUtils.invokeMethod(adapter, "classify",
                new IOException((String) null))).isEqualTo(TaskErrorCode.HANDLER_FAILED);
    }

    @Test
    void loggingOutputStreamHandlesSingleBytesLargeChunksAndEmptyRuntimeOnlyChunks() throws Exception {
        TaskExecutionContext context = mock(TaskExecutionContext.class);
        Class<?> streamClass = Class.forName(
                "cn.rvport.backend.environment.runtime.ApacheMinaSshClientAdapter$LoggingOutputStream");
        Constructor<?> constructor = streamClass.getDeclaredConstructor(
                ByteArrayOutputStream.class, TaskExecutionContext.class, TaskLogType.class,
                boolean.class, Object.class);
        constructor.setAccessible(true);
        OutputStream plain = (OutputStream) constructor.newInstance(
                new ByteArrayOutputStream(), context, TaskLogType.STDERR, false, new Object());
        Method flush = streamClass.getDeclaredMethod("flushRemainder");
        flush.setAccessible(true);

        plain.write('a');
        plain.write('\n');
        plain.write("b".repeat(4000).getBytes(StandardCharsets.UTF_8));
        flush.invoke(plain);
        flush.invoke(plain);
        verify(context, org.mockito.Mockito.atLeastOnce()).log(
                org.mockito.Mockito.eq(TaskLogType.COMBINED), org.mockito.Mockito.contains("[STDERR]"));

        TaskExecutionContext strippedContext = mock(TaskExecutionContext.class);
        OutputStream stripped = (OutputStream) constructor.newInstance(
                new ByteArrayOutputStream(), strippedContext, TaskLogType.STDOUT, true, new Object());
        stripped.write("RVPORT_REMOTE_PID=1\nRVPORT_REMOTE_PGID=2\n".getBytes(StandardCharsets.UTF_8));
        flush.invoke(stripped);
        org.mockito.Mockito.verifyNoInteractions(strippedContext);
    }

    @Test
    void loggingOutputStreamPreservesTrailingLineStateAndHandlesNullMergedText() throws Exception {
        TaskExecutionContext context = mock(TaskExecutionContext.class);
        Class<?> streamClass = Class.forName(
                "cn.rvport.backend.environment.runtime.ApacheMinaSshClientAdapter$LoggingOutputStream");
        Constructor<?> constructor = streamClass.getDeclaredConstructor(
                ByteArrayOutputStream.class, TaskExecutionContext.class, TaskLogType.class,
                boolean.class, Object.class);
        constructor.setAccessible(true);
        Object stream = constructor.newInstance(
                new ByteArrayOutputStream(), context, TaskLogType.STDOUT, true, new Object());

        assertThat((String) ReflectionTestUtils.invokeMethod(stream, "stripRuntimeLines", "visible"))
                .isEqualTo("visible");
        assertThat((String) ReflectionTestUtils.invokeMethod(stream, "stripRuntimeLines", "visible\n"))
                .isEqualTo("visible" + System.lineSeparator());
        assertThat((String) ReflectionTestUtils.invokeMethod(stream, "mergedChunk", TaskLogType.STDOUT, null))
                .isEmpty();
        assertThat((String) ReflectionTestUtils.invokeMethod(stream, "mergedChunk", TaskLogType.STDOUT, "a\nb"))
                .isEqualTo("[STDOUT] a" + System.lineSeparator() + "[STDOUT] b" + System.lineSeparator());
    }

    @Test
    void streamOutputWithoutContextStillConsumesOutputButReturnsEmptyPayload() throws Exception {
        SshFixture fixture = fixture("visible\n", "warning\n", EnumSet.of(ClientChannelEvent.CLOSED), 0);
        ApacheMinaSshClientAdapter adapter = adapter(fixture);
        SshCommandRequest request = new SshCommandRequest(
                target(CredentialKind.SSH_PASSWORD), null, "true", null, true,
                Duration.ofSeconds(1), Duration.ofSeconds(1), null);

        SshCommandResult result = adapter.execute(request);

        assertThat(result.exitCode()).isZero();
        assertThat(result.stdout()).isEmpty();
        assertThat(result.stderr()).isEmpty();
    }

    @Test
    void cancellationTargetsProcessGroupThenFallsBackToPidAndAlwaysClosesChannel() throws Exception {
        ApacheMinaSshClientAdapter adapter = new ApacheMinaSshClientAdapter();
        ClientSession session = mock(ClientSession.class);
        ClientChannel running = mock(ClientChannel.class);
        ChannelExec kill = mock(ChannelExec.class);
        OpenFuture open = mock(OpenFuture.class);
        when(session.createExecChannel(anyString())).thenReturn(kill);
        when(kill.open()).thenReturn(open);
        when(open.verify(5_000)).thenReturn(open);
        when(kill.waitFor(org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.eq(10_000L)))
                .thenReturn(EnumSet.of(ClientChannelEvent.CLOSED));
        TaskExecutionContext context = mock(TaskExecutionContext.class);
        SshCommandRequest request = new SshCommandRequest(
                target(CredentialKind.SSH_PASSWORD), null, "sleep", null, false,
                Duration.ofSeconds(1), Duration.ofSeconds(1), context);

        ReflectionTestUtils.invokeMethod(adapter, "cancelRemote", session, running,
                output("RVPORT_REMOTE_PID=11\nRVPORT_REMOTE_PGID=12\n"), request);
        verify(session).createExecChannel(org.mockito.ArgumentMatchers.contains("kill -TERM -12"));
        verify(context).registerRemoteProcess(request.target().environmentId(), 11L, 12L, "rvport-ssh-command");
        verify(running).close(false);

        org.mockito.Mockito.clearInvocations(session, running, context);
        ReflectionTestUtils.invokeMethod(adapter, "cancelRemote", session, running,
                output("RVPORT_REMOTE_PID=11\nRVPORT_REMOTE_PGID=0\n"), request);
        verify(session).createExecChannel(org.mockito.ArgumentMatchers.contains("kill -TERM 11"));
        verify(running).close(false);

        org.mockito.Mockito.clearInvocations(session, running, context);
        ReflectionTestUtils.invokeMethod(adapter, "cancelRemote", session, running,
                output("ordinary output"), request);
        verify(session, org.mockito.Mockito.never()).createExecChannel(anyString());
        verify(running).close(false);
    }

    @Test
    void cancellationSuppressesKillFailureAndHandlesTargetWithoutEnvironmentId() throws Exception {
        ApacheMinaSshClientAdapter adapter = new ApacheMinaSshClientAdapter();
        ClientSession session = mock(ClientSession.class);
        ClientChannel running = mock(ClientChannel.class);
        when(session.createExecChannel(anyString())).thenThrow(new IOException("channel closed"));
        SshConnectionTarget target = new SshConnectionTarget(
                null, "host", 22, "user", null,
                new SshRuntimeCredential(CredentialKind.SSH_PASSWORD, "user", "password", null, null));
        SshCommandRequest request = new SshCommandRequest(
                target, null, "sleep", null, false,
                Duration.ofSeconds(1), Duration.ofSeconds(1), mock(TaskExecutionContext.class));

        ReflectionTestUtils.invokeMethod(adapter, "cancelRemote", session, running,
                output("RVPORT_REMOTE_PID=9\n"), request);

        verify(running).close(false);
    }

    @Test
    void uploadsFileThroughSftpAndReturnsDigest() throws Exception {
        SshFixture fixture = fixture("", "", EnumSet.of(ClientChannelEvent.CLOSED), 0);
        SftpClient sftp = mock(SftpClient.class);
        SftpClient.CloseableHandle handle = mock(SftpClient.CloseableHandle.class);
        when(sftp.open(anyString(), org.mockito.ArgumentMatchers.any(java.util.Collection.class)))
                .thenReturn(handle);
        Path source = tempDir.resolve("source.bin");
        byte[] content = "binary-content".getBytes(StandardCharsets.UTF_8);
        Files.write(source, content);
        ApacheMinaSshClientAdapter adapter = adapter(fixture, sftp);
        SshFileTransferRequest request = transferRequest(source, "/tmp/target.bin", content.length, null);

        SshFileTransferResult result = adapter.upload(request);

        assertThat(result.sizeBytes()).isEqualTo(content.length);
        assertThat(result.sha256()).isEqualTo(sha256(content));
        verify(sftp).write(org.mockito.Mockito.eq(handle), org.mockito.Mockito.eq(0L),
                org.mockito.ArgumentMatchers.any(byte[].class), org.mockito.Mockito.eq(0),
                org.mockito.Mockito.eq(content.length));
        verify(sftp).rename(org.mockito.ArgumentMatchers.contains("/tmp/target.bin.part-"),
                org.mockito.Mockito.eq("/tmp/target.bin"));
    }

    @Test
    void downloadsFileAtomicallyThroughSftpAndReturnsDigest() throws Exception {
        SshFixture fixture = fixture("", "", EnumSet.of(ClientChannelEvent.CLOSED), 0);
        SftpClient sftp = mock(SftpClient.class);
        SftpClient.CloseableHandle handle = mock(SftpClient.CloseableHandle.class);
        SftpClient.Attributes attributes = mock(SftpClient.Attributes.class);
        byte[] content = "download-content".getBytes(StandardCharsets.UTF_8);
        when(attributes.getSize()).thenReturn((long) content.length);
        when(sftp.stat("/tmp/source.bin")).thenReturn(attributes);
        when(sftp.open(org.mockito.Mockito.eq("/tmp/source.bin"),
                org.mockito.ArgumentMatchers.any(SftpClient.OpenMode[].class))).thenReturn(handle);
        when(sftp.read(org.mockito.Mockito.eq(handle), org.mockito.Mockito.eq(0L),
                org.mockito.ArgumentMatchers.any(byte[].class), org.mockito.Mockito.eq(0),
                org.mockito.Mockito.eq(content.length))).thenAnswer(invocation -> {
                    byte[] buffer = invocation.getArgument(2);
                    System.arraycopy(content, 0, buffer, 0, content.length);
                    return content.length;
                });
        Path destination = tempDir.resolve("nested/destination.bin");
        ApacheMinaSshClientAdapter adapter = adapter(fixture, sftp);

        SshFileTransferResult result = adapter.download(
                transferRequest(destination, "/tmp/source.bin", 1024, null));

        assertThat(Files.readAllBytes(destination)).isEqualTo(content);
        assertThat(result.sizeBytes()).isEqualTo(content.length);
        assertThat(result.sha256()).isEqualTo(sha256(content));
    }

    @Test
    void enforcesTransferLimitsAndCleansPartialFiles() throws Exception {
        SshFixture uploadFixture = fixture("", "", EnumSet.of(ClientChannelEvent.CLOSED), 0);
        Path source = tempDir.resolve("too-large.bin");
        Files.write(source, new byte[5]);
        ApacheMinaSshClientAdapter uploadAdapter = adapter(uploadFixture, mock(SftpClient.class));
        assertThatThrownBy(() -> uploadAdapter.upload(transferRequest(source, "/tmp/a", 4, null)))
                .isInstanceOfSatisfying(SshRuntimeException.class,
                        ex -> assertThat(ex.errorCode()).isEqualTo(TaskErrorCode.INPUT_INVALID));

        SshFixture downloadFixture = fixture("", "", EnumSet.of(ClientChannelEvent.CLOSED), 0);
        SftpClient sftp = mock(SftpClient.class);
        SftpClient.Attributes attributes = mock(SftpClient.Attributes.class);
        when(attributes.getSize()).thenReturn(5L);
        when(sftp.stat("/tmp/a")).thenReturn(attributes);
        Path destination = tempDir.resolve("limited.bin");
        assertThatThrownBy(() -> adapter(downloadFixture, sftp).download(
                transferRequest(destination, "/tmp/a", 4, null)))
                .isInstanceOfSatisfying(SshRuntimeException.class,
                        ex -> assertThat(ex.errorCode()).isEqualTo(TaskErrorCode.INPUT_INVALID));
        assertThat(destination).doesNotExist();
    }

    @Test
    void rejectsTruncatedDownloadAndHonorsCancellationAndTimeout() throws Exception {
        SshFixture fixture = fixture("", "", EnumSet.of(ClientChannelEvent.CLOSED), 0);
        SftpClient sftp = mock(SftpClient.class);
        SftpClient.CloseableHandle handle = mock(SftpClient.CloseableHandle.class);
        SftpClient.Attributes attributes = mock(SftpClient.Attributes.class);
        when(attributes.getSize()).thenReturn(4L);
        when(sftp.stat("/tmp/truncated")).thenReturn(attributes);
        when(sftp.open(org.mockito.Mockito.eq("/tmp/truncated"),
                org.mockito.ArgumentMatchers.any(SftpClient.OpenMode[].class))).thenReturn(handle);
        when(sftp.read(org.mockito.Mockito.eq(handle), org.mockito.Mockito.eq(0L),
                org.mockito.ArgumentMatchers.any(byte[].class), org.mockito.Mockito.eq(0), org.mockito.Mockito.eq(4)))
                .thenReturn(-1);
        Path destination = tempDir.resolve("truncated.bin");
        assertThatThrownBy(() -> adapter(fixture, sftp).download(
                transferRequest(destination, "/tmp/truncated", 10, null)))
                .isInstanceOf(SshRuntimeException.class).hasMessage("SSH 文件下载失败");
        assertThat(destination).doesNotExist();

        ApacheMinaSshClientAdapter adapter = new ApacheMinaSshClientAdapter();
        TaskExecutionContext cancelled = mock(TaskExecutionContext.class);
        org.mockito.Mockito.doThrow(new cn.rvport.backend.worker.TaskCancelledException("cancelled"))
                .when(cancelled).throwIfCancellationRequested();
        SshFileTransferRequest cancelledRequest = transferRequest(tempDir.resolve("unused"), "/tmp/a", 10, cancelled);
        assertThatThrownBy(() -> ReflectionTestUtils.invokeMethod(adapter, "checkTransferState",
                cancelledRequest, java.time.Instant.now())).isInstanceOf(cn.rvport.backend.worker.TaskCancelledException.class);

        SshFileTransferRequest timeoutRequest = new SshFileTransferRequest(target(CredentialKind.SSH_PASSWORD), null,
                tempDir.resolve("unused"), "/tmp/a", 10, Duration.ofSeconds(1), Duration.ofMillis(1), null);
        assertThatThrownBy(() -> ReflectionTestUtils.invokeMethod(adapter, "checkTransferState",
                timeoutRequest, java.time.Instant.now().minusSeconds(1)))
                .isInstanceOfSatisfying(SshRuntimeException.class,
                        ex -> assertThat(ex.errorCode()).isEqualTo(TaskErrorCode.REMOTE_COMMAND_FAILED));
    }

    private ByteArrayOutputStream output(String value) throws IOException {
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        output.write(value.getBytes(StandardCharsets.UTF_8));
        return output;
    }

    private SshFileTransferRequest transferRequest(Path local, String remote, long maxBytes,
                                                   TaskExecutionContext context) {
        return new SshFileTransferRequest(target(CredentialKind.SSH_PASSWORD), null, local, remote, maxBytes,
                Duration.ofSeconds(1), Duration.ofSeconds(10), context);
    }

    private String sha256(byte[] content) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(content));
    }

    private SshConnectionTarget target(CredentialKind kind) {
        return new SshConnectionTarget(
                UUID.randomUUID(), "host.example", 22, "tester", "/work",
                new SshRuntimeCredential(kind, "tester", "password", "private-key", null));
    }

    private SshFixture fixture(
            String stdout,
            String stderr,
            java.util.Set<ClientChannelEvent> events,
            Integer exitStatus
    ) throws Exception {
        SshClient client = mock(SshClient.class);
        ConnectFuture connect = mock(ConnectFuture.class);
        ClientSession session = mock(ClientSession.class);
        AuthFuture auth = mock(AuthFuture.class);
        ClientChannel channel = mock(ClientChannel.class);
        OpenFuture open = mock(OpenFuture.class);
        AtomicReference<OutputStream> out = new AtomicReference<>();
        AtomicReference<OutputStream> err = new AtomicReference<>();

        when(client.connect(anyString(), anyString(), org.mockito.ArgumentMatchers.anyInt())).thenReturn(connect);
        when(connect.verify(anyLong())).thenReturn(connect);
        when(connect.getSession()).thenReturn(session);
        when(session.auth()).thenReturn(auth);
        when(auth.verify(anyLong())).thenReturn(auth);
        doAnswer(invocation -> {
            out.set(invocation.getArgument(0));
            return null;
        }).when(channel).setOut(org.mockito.ArgumentMatchers.any(OutputStream.class));
        doAnswer(invocation -> {
            err.set(invocation.getArgument(0));
            return null;
        }).when(channel).setErr(org.mockito.ArgumentMatchers.any(OutputStream.class));
        when(channel.open()).thenAnswer(invocation -> {
            out.get().write(stdout.getBytes(StandardCharsets.UTF_8));
            err.get().write(stderr.getBytes(StandardCharsets.UTF_8));
            return open;
        });
        when(open.verify(anyLong())).thenReturn(open);
        when(channel.waitFor(org.mockito.ArgumentMatchers.any(), anyLong())).thenReturn(events);
        when(channel.getExitStatus()).thenReturn(exitStatus);
        return new SshFixture(client, session, channel, new AtomicReference<>());
    }

    private ApacheMinaSshClientAdapter adapter(SshFixture fixture) {
        return new ApacheMinaSshClientAdapter(() -> fixture.client, (session, command) -> {
            assertThat(session).isSameAs(fixture.session);
            fixture.command.set(command);
            return fixture.channel;
        });
    }

    private ApacheMinaSshClientAdapter adapter(SshFixture fixture, SftpClient sftp) {
        return new ApacheMinaSshClientAdapter(() -> fixture.client, (session, command) -> fixture.channel,
                session -> sftp);
    }

    private record SshFixture(
            SshClient client,
            ClientSession session,
            ClientChannel channel,
            AtomicReference<String> command
    ) {
    }
}
