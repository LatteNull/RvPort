package cn.rvport.backend.environment.runtime;

import cn.rvport.backend.credential.CredentialKind;
import cn.rvport.backend.task.TaskErrorCode;
import cn.rvport.backend.task.TaskLogType;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.security.KeyPair;
import java.security.MessageDigest;
import java.time.Duration;
import java.time.Instant;
import java.util.EnumSet;
import java.util.HexFormat;
import java.util.Set;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.apache.sshd.client.SshClient;
import org.apache.sshd.client.channel.ClientChannel;
import org.apache.sshd.client.channel.ClientChannelEvent;
import org.apache.sshd.client.future.ConnectFuture;
import org.apache.sshd.client.session.ClientSession;
import org.apache.sshd.client.session.forward.ExplicitPortForwardingTracker;
import org.apache.sshd.common.NamedResource;
import org.apache.sshd.common.config.keys.FilePasswordProvider;
import org.apache.sshd.common.util.net.SshdSocketAddress;
import org.apache.sshd.common.util.security.SecurityUtils;
import org.apache.sshd.sftp.client.SftpClient;
import org.apache.sshd.sftp.client.SftpClientFactory;
import org.springframework.stereotype.Component;

@Component
public class ApacheMinaSshClientAdapter implements SshClientAdapter {

    private static final Pattern REMOTE_PID = Pattern.compile("(?m)^RVPORT_REMOTE_PID=(\\d+)\\s*$");
    private static final Pattern REMOTE_PGID = Pattern.compile("(?m)^RVPORT_REMOTE_PGID=(\\d+)\\s*$");
    private final SshClientFactory clientFactory;
    private final SshChannelFactory channelFactory;
    private final SftpClientProvider sftpClientProvider;

    public ApacheMinaSshClientAdapter() {
        this(SshClient::setUpDefaultClient, ClientSession::createExecChannel,
                session -> SftpClientFactory.instance().createSftpClient(session));
    }

    ApacheMinaSshClientAdapter(SshClientFactory clientFactory) {
        this(clientFactory, ClientSession::createExecChannel,
                session -> SftpClientFactory.instance().createSftpClient(session));
    }

    ApacheMinaSshClientAdapter(SshClientFactory clientFactory, SshChannelFactory channelFactory) {
        this(clientFactory, channelFactory, session -> SftpClientFactory.instance().createSftpClient(session));
    }

    ApacheMinaSshClientAdapter(SshClientFactory clientFactory, SshChannelFactory channelFactory,
                               SftpClientProvider sftpClientProvider) {
        this.clientFactory = clientFactory;
        this.channelFactory = channelFactory;
        this.sftpClientProvider = sftpClientProvider;
    }

    @Override
    public SshCommandResult execute(SshCommandRequest request) {
        Instant started = Instant.now();
        try (SshClient client = clientFactory.create()) {
            client.start();
            if (request.jumpHost() == null) {
                return executeDirect(client, request, started);
            }
            return executeViaJumpHost(client, request, started);
        } catch (SshRuntimeException ex) {
            throw ex;
        } catch (Exception ex) {
            throw new SshRuntimeException(classify(ex), "SSH 命令执行失败", ex);
        }
    }

    private SshCommandResult executeDirect(SshClient client, SshCommandRequest request, Instant started) throws Exception {
        try (ClientSession session = connectAndAuthenticate(client, request.target(), request.connectTimeout())) {
            return executeCommand(session, request, started);
        }
    }

    private SshCommandResult executeViaJumpHost(SshClient client, SshCommandRequest request, Instant started) throws Exception {
        try (ClientSession jumpSession = connectAndAuthenticate(client, request.jumpHost(), request.connectTimeout());
             ExplicitPortForwardingTracker forwarding = jumpSession.createLocalPortForwardingTracker(
                     new SshdSocketAddress(SshdSocketAddress.LOCALHOST_IPV4, 0),
                     new SshdSocketAddress(request.target().host(), request.target().port())
             )) {
            SshdSocketAddress localAddress = forwarding.getBoundAddress();
            SshConnectionTarget forwardedTarget = new SshConnectionTarget(
                    request.target().environmentId(),
                    localAddress.getHostName(),
                    localAddress.getPort(),
                    request.target().username(),
                    request.target().workingDirectory(),
                    request.target().credential()
            );
            SshClient targetClient = clientFactory.create();
            try {
                targetClient.start();
                SshCommandResult result = executeForwardedTarget(targetClient, forwardedTarget, request, started);
                forwarding.close();
                return result;
            } finally {
                targetClient.close();
            }
        }
    }

    private SshCommandResult executeForwardedTarget(
            SshClient targetClient,
            SshConnectionTarget forwardedTarget,
            SshCommandRequest request,
            Instant started
    ) throws Exception {
        try (ClientSession targetSession = connectAndAuthenticate(targetClient, forwardedTarget, request.connectTimeout())) {
            return executeCommand(targetSession, request, started);
        }
    }

    private ClientSession connectAndAuthenticate(SshClient client, SshConnectionTarget target, Duration connectTimeout) throws Exception {
        ConnectFuture connect = client.connect(target.username(), target.host(), target.port());
        ClientSession session = connect.verify(connectTimeout.toMillis()).getSession();
        authenticate(session, target);
        session.auth().verify(connectTimeout.toMillis());
        return session;
    }

    private void authenticate(ClientSession session, SshConnectionTarget target) throws Exception {
        SshRuntimeCredential credential = target.credential();
        if (credential.kind() == CredentialKind.SSH_PASSWORD) {
            session.addPasswordIdentity(credential.password());
            return;
        }
        if (credential.kind() == CredentialKind.SSH_KEY) {
            FilePasswordProvider passwordProvider = credential.passphrase() == null || credential.passphrase().isBlank()
                    ? FilePasswordProvider.EMPTY
                    : FilePasswordProvider.of(credential.passphrase());
            Iterable<KeyPair> keyPairs = SecurityUtils.loadKeyPairIdentities(
                    null,
                    NamedResource.ofName("credential-" + credential.kind().name()),
                    new ByteArrayInputStream(credential.privateKey().getBytes(StandardCharsets.UTF_8)),
                    passwordProvider
            );
            for (KeyPair keyPair : keyPairs) {
                session.addPublicKeyIdentity(keyPair);
            }
            return;
        }
        throw new SshRuntimeException(TaskErrorCode.CREDENTIAL_INVALID, "SSH 凭据类型不正确", null);
    }

    private String classify(Exception ex) {
        String text = (ex.getClass().getName() + " " + ex.getMessage()).toLowerCase();
        Throwable cause = ex.getCause();
        while (cause != null) {
            text += " " + cause.getClass().getName().toLowerCase() + " " + String.valueOf(cause.getMessage()).toLowerCase();
            cause = cause.getCause();
        }
        if (text.contains("auth") || text.contains("credential") || text.contains("keypair") || text.contains("private key")
                || text.contains("bad password") || text.contains("permission denied")) {
            return TaskErrorCode.CREDENTIAL_INVALID;
        }
        return TaskErrorCode.HANDLER_FAILED;
    }

    private SshCommandResult executeCommand(
            ClientSession session,
            SshCommandRequest request,
            Instant started
    ) throws Exception {
        try (ByteArrayOutputStream stdout = new ByteArrayOutputStream();
             ByteArrayOutputStream stderr = new ByteArrayOutputStream();
             ClientChannel channel = channelFactory.create(session, wrappedCommand(request.command(), hasStdin(request)))) {
            LoggingOutputStream stdoutStream = null;
            LoggingOutputStream stderrStream = null;
            if (request.streamOutput() && request.executionContext() != null) {
                Object mergeLock = new Object();
                stdoutStream = new LoggingOutputStream(stdout, request.executionContext(), TaskLogType.STDOUT, true, mergeLock);
                stderrStream = new LoggingOutputStream(stderr, request.executionContext(), TaskLogType.STDERR, false, mergeLock);
                channel.setOut(stdoutStream);
                channel.setErr(stderrStream);
            } else {
                channel.setOut(stdout);
                channel.setErr(stderr);
            }
            channel.open().verify(request.connectTimeout().toMillis());
            if (hasStdin(request)) {
                try (OutputStream input = channel.getInvertedIn()) {
                    writeStdin(request, input);
                    input.flush();
                }
            }
            if (request.executionContext() != null) {
                request.executionContext().registerCancellableResource(() ->
                        cancelRemote(session, channel, stdout, request));
            }
            Set<ClientChannelEvent> events = channel.waitFor(EnumSet.of(ClientChannelEvent.CLOSED), request.commandTimeout().toMillis());
            if (!events.contains(ClientChannelEvent.CLOSED)) {
                channel.close(false);
                throw new SshRuntimeException(
                        TaskErrorCode.REMOTE_COMMAND_FAILED,
                        "SSH 命令执行超时",
                        null
                );
            }
            if (stdoutStream != null) {
                stdoutStream.flushRemainder();
            }
            if (stderrStream != null) {
                stderrStream.flushRemainder();
            }
            Integer exitStatus = channel.getExitStatus();
            String stdoutText = stdout.toString(StandardCharsets.UTF_8);
            registerRemoteProcess(request, stdoutText);
            String strippedStdout = stripRvportRuntimeLines(stdoutText);
            String stderrText = stderr.toString(StandardCharsets.UTF_8);
            return new SshCommandResult(
                    exitStatus == null ? -1 : exitStatus,
                    request.streamOutput() ? "" : strippedStdout,
                    request.streamOutput() ? "" : stderrText,
                    Duration.between(started, Instant.now())
            );
        }
    }

    private boolean hasStdin(SshCommandRequest request) {
        return request.stdin() != null || request.stdinStream() != null;
    }

    private void writeStdin(SshCommandRequest request, OutputStream input) throws IOException {
        if (request.stdinStream() != null) {
            try (InputStream source = request.stdinStream()) {
                source.transferTo(input);
            }
            return;
        }
        input.write(request.stdin().getBytes(StandardCharsets.UTF_8));
    }

    private void cancelRemote(ClientSession session, ClientChannel channel, ByteArrayOutputStream stdout, SshCommandRequest request) {
        String currentStdout = stdout.toString(StandardCharsets.UTF_8);
        Long pgid = firstLong(REMOTE_PGID, currentStdout);
        Long pid = firstLong(REMOTE_PID, currentStdout);
        if (request.executionContext() != null && (pid != null || pgid != null)) {
            request.executionContext().registerRemoteProcess(request.target().environmentId(), pid, pgid, "rvport-ssh-command");
        }
        try {
            String target = pgid != null && pgid > 0 ? "-" + pgid : pid == null ? null : pid.toString();
            if (target != null) {
                String killCommand = "sh -lc " + shellQuote("kill -TERM " + target + " 2>/dev/null || true; sleep 2; kill -KILL " + target + " 2>/dev/null || true");
                try (ClientChannel kill = session.createExecChannel(killCommand)) {
                    kill.open().verify(5_000);
                    kill.waitFor(EnumSet.of(ClientChannelEvent.CLOSED), 10_000);
                }
            }
        } catch (Exception ignored) {
            // 远程 kill 失败后仍关闭当前 channel，清理失败状态由取消 listener 记录。
        } finally {
            if (request.target().environmentId() != null) {
                // environmentId 被传入是为了保证取消资源和目标环境绑定，避免未来误删该参数。
            }
            channel.close(false);
        }
    }

    private void registerRemoteProcess(SshCommandRequest request, String stdout) {
        if (request.executionContext() == null) {
            return;
        }
        Long pid = firstLong(REMOTE_PID, stdout);
        Long pgid = firstLong(REMOTE_PGID, stdout);
        if (pid != null || pgid != null) {
            request.executionContext().registerRemoteProcess(request.target().environmentId(), pid, pgid, "rvport-ssh-command");
        }
    }

    private String wrappedCommand(String command, boolean requiresStdin) {
        String script;
        if (requiresStdin) {
            script = """
                    pid=$$
                    pgid=$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ' || true)
                    [ -z "$pgid" ] && pgid="$pid"
                    printf 'RVPORT_REMOTE_PID=%s\\n' "$pid"
                    printf 'RVPORT_REMOTE_PGID=%s\\n' "$pgid"
                    ( __RVPORT_COMMAND__ )
                    exit $?
                    """.replace("__RVPORT_COMMAND__", command == null ? "" : command);
            return "sh -lc " + shellQuote(script);
        }
        script = """
                ( __RVPORT_COMMAND__ ) &
                pid=$!
                pgid=$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ' || true)
                [ -z "$pgid" ] && pgid="$pid"
                printf 'RVPORT_REMOTE_PID=%s\\n' "$pid"
                printf 'RVPORT_REMOTE_PGID=%s\\n' "$pgid"
                wait "$pid"
                exit $?
                """.replace("__RVPORT_COMMAND__", command == null ? "" : command);
        return "sh -lc " + shellQuote(script);
    }

    private Long firstLong(Pattern pattern, String text) {
        Matcher matcher = pattern.matcher(text == null ? "" : text);
        return matcher.find() ? Long.parseLong(matcher.group(1)) : null;
    }

    private String stripRvportRuntimeLines(String stdout) {
        return (stdout == null ? "" : stdout).lines()
                .filter(line -> !line.startsWith("RVPORT_REMOTE_PID="))
                .filter(line -> !line.startsWith("RVPORT_REMOTE_PGID="))
                .collect(java.util.stream.Collectors.joining(System.lineSeparator()));
    }

    private String shellQuote(String value) {
        return "'" + value.replace("'", "'\"'\"'") + "'";
    }

    private static final class LoggingOutputStream extends OutputStream {

        private final ByteArrayOutputStream delegate;
        private final cn.rvport.backend.worker.TaskExecutionContext context;
        private final TaskLogType logType;
        private final boolean stripRuntimeLines;
        private final Object mergeLock;
        private final ByteArrayOutputStream pending = new ByteArrayOutputStream();

        private LoggingOutputStream(
                ByteArrayOutputStream delegate,
                cn.rvport.backend.worker.TaskExecutionContext context,
                TaskLogType logType,
                boolean stripRuntimeLines,
                Object mergeLock
        ) {
            this.delegate = delegate;
            this.context = context;
            this.logType = logType;
            this.stripRuntimeLines = stripRuntimeLines;
            this.mergeLock = mergeLock;
        }

        @Override
        public synchronized void write(int b) throws IOException {
            delegate.write(b);
            pending.write(b);
            if (b == '\n' || pending.size() >= 4000) {
                flushRemainder();
            }
        }

        @Override
        public synchronized void write(byte[] b, int off, int len) throws IOException {
            delegate.write(b, off, len);
            for (int i = 0; i < len; i++) {
                pending.write(b[off + i]);
                if (b[off + i] == '\n' || pending.size() >= 4000) {
                    flushRemainder();
                }
            }
        }

        synchronized void flushRemainder() {
            if (pending.size() == 0) {
                return;
            }
            String text = pending.toString(StandardCharsets.UTF_8);
            pending.reset();
            if (stripRuntimeLines) {
                text = stripRuntimeLines(text);
                if (text.isBlank()) {
                    return;
                }
            }
            synchronized (mergeLock) {
                context.log(logType, text);
                context.log(TaskLogType.COMBINED, mergedChunk(logType, text));
            }
        }

        private String mergedChunk(TaskLogType logType, String text) {
            String prefix = "[" + logType.name() + "] ";
            String normalized = text == null ? "" : text;
            StringBuilder merged = new StringBuilder();
            String[] lines = normalized.split("\\R", -1);
            for (int i = 0; i < lines.length; i++) {
                if (i == lines.length - 1 && lines[i].isEmpty()) {
                    continue;
                }
                merged.append(prefix).append(lines[i]).append(System.lineSeparator());
            }
            return merged.toString();
        }

        private String stripRuntimeLines(String text) {
            return text.lines()
                    .filter(line -> !line.startsWith("RVPORT_REMOTE_PID="))
                    .filter(line -> !line.startsWith("RVPORT_REMOTE_PGID="))
                    .collect(java.util.stream.Collectors.joining(System.lineSeparator(), "", text.endsWith("\n") ? System.lineSeparator() : ""));
        }
    }

    @Override
    public SshFileTransferResult upload(SshFileTransferRequest request) {
        return transfer(request, this::uploadToSession, "SSH 文件上传失败");
    }

    @Override
    public SshFileTransferResult download(SshFileTransferRequest request) {
        return transfer(request, this::downloadFromSession, "SSH 文件下载失败");
    }

    private SshFileTransferResult transfer(
            SshFileTransferRequest request,
            TransferOperation operation,
            String failureMessage
    ) {
        Instant started = Instant.now();
        try (SshClient client = clientFactory.create()) {
            client.start();
            if (request.jumpHost() == null) {
                try (ClientSession session = connectAndAuthenticate(client, request.target(), request.connectTimeout())) {
                    return operation.transfer(session, request, started);
                }
            }
            try (ClientSession jumpSession = connectAndAuthenticate(client, request.jumpHost(), request.connectTimeout());
                 ExplicitPortForwardingTracker forwarding = jumpSession.createLocalPortForwardingTracker(
                         new SshdSocketAddress(SshdSocketAddress.LOCALHOST_IPV4, 0),
                         new SshdSocketAddress(request.target().host(), request.target().port())
                 )) {
                SshdSocketAddress localAddress = forwarding.getBoundAddress();
                SshConnectionTarget forwardedTarget = new SshConnectionTarget(
                        request.target().environmentId(),
                        localAddress.getHostName(),
                        localAddress.getPort(),
                        request.target().username(),
                        request.target().workingDirectory(),
                        request.target().credential()
                );
                try (SshClient targetClient = clientFactory.create()) {
                    targetClient.start();
                    try (ClientSession targetSession = connectAndAuthenticate(
                            targetClient, forwardedTarget, request.connectTimeout())) {
                        return operation.transfer(targetSession, request, started);
                    }
                }
            }
        } catch (SshRuntimeException ex) {
            throw ex;
        } catch (Exception ex) {
            throw new SshRuntimeException(classify(ex), failureMessage, ex);
        }
    }

    private SshFileTransferResult uploadToSession(
            ClientSession session,
            SshFileTransferRequest request,
            Instant started
    ) throws Exception {
        long size = Files.size(request.localPath());
        if (size > request.maxBytes()) {
            throw new SshRuntimeException(TaskErrorCode.INPUT_INVALID, "SSH 上传文件超出大小限制", null);
        }
        String temporaryRemotePath = request.remotePath() + ".part-" + UUID.randomUUID();
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        long written = 0;
        try (SftpClient sftp = sftpClientProvider.create(session);
             InputStream input = Files.newInputStream(request.localPath());
             SftpClient.CloseableHandle handle = sftp.open(temporaryRemotePath,
                     EnumSet.of(SftpClient.OpenMode.Write, SftpClient.OpenMode.Create, SftpClient.OpenMode.Truncate))) {
            byte[] buffer = new byte[64 * 1024];
            int read;
            while ((read = input.read(buffer)) >= 0) {
                checkTransferState(request, started);
                if (read == 0) {
                    continue;
                }
                written = Math.addExact(written, read);
                if (written > request.maxBytes()) {
                    throw new SshRuntimeException(TaskErrorCode.INPUT_INVALID, "SSH 上传文件超出大小限制", null);
                }
                digest.update(buffer, 0, read);
                sftp.write(handle, written - read, buffer, 0, read);
            }
            sftp.rename(temporaryRemotePath, request.remotePath());
        } catch (Exception ex) {
            removeRemotePartial(session, temporaryRemotePath);
            throw ex;
        }
        return new SshFileTransferResult(written, HexFormat.of().formatHex(digest.digest()),
                Duration.between(started, Instant.now()));
    }

    private SshFileTransferResult downloadFromSession(
            ClientSession session,
            SshFileTransferRequest request,
            Instant started
    ) throws Exception {
        Path temporaryLocalPath = request.localPath().resolveSibling(
                request.localPath().getFileName() + ".part-" + UUID.randomUUID());
        Files.createDirectories(request.localPath().toAbsolutePath().normalize().getParent());
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        long readTotal = 0;
        try (SftpClient sftp = sftpClientProvider.create(session)) {
            long remoteSize = sftp.stat(request.remotePath()).getSize();
            if (remoteSize < 0 || remoteSize > request.maxBytes()) {
                throw new SshRuntimeException(TaskErrorCode.INPUT_INVALID, "SSH 下载文件超出大小限制", null);
            }
            try (SftpClient.CloseableHandle handle = sftp.open(request.remotePath(), SftpClient.OpenMode.Read);
                 OutputStream output = Files.newOutputStream(temporaryLocalPath)) {
                byte[] buffer = new byte[64 * 1024];
                while (readTotal < remoteSize) {
                    checkTransferState(request, started);
                    int requested = (int) Math.min(buffer.length, remoteSize - readTotal);
                    int read = sftp.read(handle, readTotal, buffer, 0, requested);
                    if (read < 0) {
                        break;
                    }
                    if (read == 0) {
                        continue;
                    }
                    readTotal += read;
                    digest.update(buffer, 0, read);
                    output.write(buffer, 0, read);
                }
            }
            if (readTotal != remoteSize) {
                throw new IOException("SSH 下载文件在传输期间被截断");
            }
            try {
                Files.move(temporaryLocalPath, request.localPath(), StandardCopyOption.ATOMIC_MOVE,
                        StandardCopyOption.REPLACE_EXISTING);
            } catch (java.nio.file.AtomicMoveNotSupportedException ex) {
                Files.move(temporaryLocalPath, request.localPath(), StandardCopyOption.REPLACE_EXISTING);
            }
        } finally {
            Files.deleteIfExists(temporaryLocalPath);
        }
        return new SshFileTransferResult(readTotal, HexFormat.of().formatHex(digest.digest()),
                Duration.between(started, Instant.now()));
    }

    private void checkTransferState(SshFileTransferRequest request, Instant started) {
        if (request.executionContext() != null) {
            request.executionContext().throwIfCancellationRequested();
        }
        if (Duration.between(started, Instant.now()).compareTo(request.transferTimeout()) > 0) {
            throw new SshRuntimeException(TaskErrorCode.REMOTE_COMMAND_FAILED, "SSH 文件传输超时", null);
        }
    }

    private void removeRemotePartial(ClientSession session, String path) {
        try (SftpClient sftp = sftpClientProvider.create(session)) {
            sftp.remove(path);
        } catch (Exception ignored) {
            // 临时文件清理由远端任务目录清理作为最后兜底。
        }
    }

    @FunctionalInterface
    interface SshClientFactory {
        SshClient create();
    }

    @FunctionalInterface
    interface SshChannelFactory {
        ClientChannel create(ClientSession session, String command) throws IOException;
    }

    @FunctionalInterface
    interface SftpClientProvider {
        SftpClient create(ClientSession session) throws IOException;
    }

    @FunctionalInterface
    private interface TransferOperation {
        SshFileTransferResult transfer(
                ClientSession session,
                SshFileTransferRequest request,
                Instant started
        ) throws Exception;
    }
}
