package cn.rvport.backend.buildvalidation.bitcode;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.config.RvPortProperties;
import cn.rvport.backend.credential.CredentialKind;
import cn.rvport.backend.environment.runtime.SshClientAdapter;
import cn.rvport.backend.environment.runtime.SshCommandRequest;
import cn.rvport.backend.environment.runtime.SshCommandResult;
import cn.rvport.backend.environment.runtime.SshConnectionTarget;
import cn.rvport.backend.environment.runtime.SshFileTransferResult;
import cn.rvport.backend.environment.runtime.SshRuntimeCredential;
import cn.rvport.backend.worker.TaskExecutionContext;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.time.Duration;
import java.util.HexFormat;
import java.util.UUID;
import org.mockito.ArgumentCaptor;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class RemoteBitcodeToolchainManagerTests {

    @TempDir
    Path tempDir;

    @Test
    void reusesValidRemoteCacheWithoutUpload() throws Exception {
        Path bundle = bundle();
        SshClientAdapter ssh = mock(SshClientAdapter.class);
        when(ssh.execute(any())).thenReturn(result(0, "RVPORT_BITCODE_TOOLCHAIN_READY"));
        RemoteBitcodeToolchainManager manager = manager(ssh, bundle, sha256(bundle));

        RemoteBitcodeToolchain toolchain = manager.ensure(request());

        assertThat(toolchain.clang()).endsWith("/bin/clang");
        assertThat(toolchain.version()).isEqualTo("21.1.8");
        org.mockito.Mockito.verify(ssh, org.mockito.Mockito.never()).upload(any());
    }

    @Test
    void deploysBundleThenValidatesPublishedCache() throws Exception {
        Path bundle = bundle();
        SshClientAdapter ssh = mock(SshClientAdapter.class);
        when(ssh.execute(any()))
                .thenReturn(result(22, ""))
                .thenReturn(result(0, "RVPORT_BITCODE_TOOLCHAIN_LOCK_ACQUIRED"))
                .thenReturn(result(0, "RVPORT_BITCODE_XZ_READY"))
                .thenReturn(result(0, "RVPORT_BITCODE_TOOLCHAIN_PUBLISHED"))
                .thenReturn(result(0, "RVPORT_BITCODE_TOOLCHAIN_READY"));
        when(ssh.upload(any())).thenReturn(new SshFileTransferResult(Files.size(bundle), sha256(bundle), Duration.ZERO));
        RemoteBitcodeToolchainManager manager = manager(ssh, bundle, sha256(bundle));

        RemoteBitcodeToolchain toolchain = manager.ensure(request());

        assertThat(toolchain.toolchainId()).isEqualTo("llvm-test");
        verify(ssh).upload(any());
        ArgumentCaptor<SshCommandRequest> commands = ArgumentCaptor.forClass(SshCommandRequest.class);
        verify(ssh, org.mockito.Mockito.times(5)).execute(commands.capture());
        assertThat(commands.getAllValues().get(2).command())
                .contains("command -v xz", "install -y xz", "install -y xz-utils", "zypper", "apk", "pacman");
    }

    @Test
    void rejectsMissingOrCorruptLocalBundleAndLockTimeout() throws Exception {
        SshClientAdapter ssh = mock(SshClientAdapter.class);
        Path missing = tempDir.resolve("missing.tar.xz");
        assertThatThrownBy(() -> manager(ssh, missing, "a".repeat(64)).ensure(request()))
                .isInstanceOfSatisfying(BitcodeRuntimeException.class,
                        ex -> assertThat(ex.reasonCode()).isEqualTo(BitcodeReasonCode.TOOLCHAIN_BUNDLE_UNAVAILABLE));

        Path bundle = bundle();
        assertThatThrownBy(() -> manager(ssh, bundle, "b".repeat(64)).ensure(request()))
                .isInstanceOfSatisfying(BitcodeRuntimeException.class,
                        ex -> assertThat(ex.reasonCode()).isEqualTo(BitcodeReasonCode.TOOLCHAIN_BUNDLE_INVALID));

        when(ssh.execute(any())).thenReturn(result(22, ""), result(31, ""));
        assertThatThrownBy(() -> manager(ssh, bundle, sha256(bundle)).ensure(request()))
                .isInstanceOfSatisfying(BitcodeRuntimeException.class,
                        ex -> assertThat(ex.reasonCode()).isEqualTo(BitcodeReasonCode.TOOLCHAIN_LOCK_TIMEOUT));
    }

    @Test
    void cleansRemoteLockWhenPublishFails() throws Exception {
        Path bundle = bundle();
        SshClientAdapter ssh = mock(SshClientAdapter.class);
        when(ssh.execute(any()))
                .thenReturn(result(22, ""))
                .thenReturn(result(0, "RVPORT_BITCODE_TOOLCHAIN_LOCK_ACQUIRED"))
                .thenReturn(result(0, "RVPORT_BITCODE_XZ_READY"))
                .thenReturn(result(44, ""))
                .thenReturn(result(0, ""));
        when(ssh.upload(any())).thenReturn(new SshFileTransferResult(Files.size(bundle), sha256(bundle), Duration.ZERO));

        assertThatThrownBy(() -> manager(ssh, bundle, sha256(bundle)).ensure(request()))
                .isInstanceOfSatisfying(BitcodeRuntimeException.class,
                        ex -> assertThat(ex.reasonCode()).isEqualTo(BitcodeReasonCode.TOOLCHAIN_CACHE_INVALID));
        verify(ssh, org.mockito.Mockito.times(5)).execute(any());
    }

    @Test
    void reportsMissingXzWhenAutomaticInstallationFailsAndCleansLock() throws Exception {
        Path bundle = bundle();
        SshClientAdapter ssh = mock(SshClientAdapter.class);
        when(ssh.execute(any()))
                .thenReturn(result(22, ""))
                .thenReturn(result(0, "RVPORT_BITCODE_TOOLCHAIN_LOCK_ACQUIRED"))
                .thenReturn(result(52, ""))
                .thenReturn(result(0, ""));

        assertThatThrownBy(() -> manager(ssh, bundle, sha256(bundle)).ensure(request()))
                .isInstanceOfSatisfying(BitcodeRuntimeException.class, ex -> {
                    assertThat(ex.reasonCode()).isEqualTo(BitcodeReasonCode.TOOLCHAIN_PREREQUISITE_UNAVAILABLE);
                    assertThat(ex).hasMessageContaining("xz");
                });
        verify(ssh, org.mockito.Mockito.never()).upload(any());
        verify(ssh, org.mockito.Mockito.times(4)).execute(any());
    }

    @Test
    void rejectsSuccessfulXzCommandWithoutReadinessMarker() throws Exception {
        Path bundle = bundle();
        SshClientAdapter ssh = mock(SshClientAdapter.class);
        when(ssh.execute(any()))
                .thenReturn(result(22, ""))
                .thenReturn(result(0, "RVPORT_BITCODE_TOOLCHAIN_LOCK_ACQUIRED"))
                .thenReturn(result(0, ""))
                .thenReturn(result(0, ""));

        assertThatThrownBy(() -> manager(ssh, bundle, sha256(bundle)).ensure(request()))
                .isInstanceOfSatisfying(BitcodeRuntimeException.class,
                        ex -> assertThat(ex.reasonCode())
                                .isEqualTo(BitcodeReasonCode.TOOLCHAIN_PREREQUISITE_UNAVAILABLE));
        verify(ssh, org.mockito.Mockito.never()).upload(any());
    }

    @Test
    void rejectsSuccessfulPublishCommandWithoutCompletionMarker() throws Exception {
        Path bundle = bundle();
        SshClientAdapter ssh = mock(SshClientAdapter.class);
        when(ssh.execute(any()))
                .thenReturn(result(22, ""))
                .thenReturn(result(0, "RVPORT_BITCODE_TOOLCHAIN_LOCK_ACQUIRED"))
                .thenReturn(result(0, "RVPORT_BITCODE_XZ_READY"))
                .thenReturn(result(0, ""))
                .thenReturn(result(0, ""));
        when(ssh.upload(any())).thenReturn(new SshFileTransferResult(Files.size(bundle), sha256(bundle), Duration.ZERO));

        assertThatThrownBy(() -> manager(ssh, bundle, sha256(bundle)).ensure(request()))
                .isInstanceOfSatisfying(BitcodeRuntimeException.class,
                        ex -> assertThat(ex.reasonCode()).isEqualTo(BitcodeReasonCode.TOOLCHAIN_CACHE_INVALID));
    }

    @Test
    void rejectsToolchainThatFailsValidationAfterPublishing() throws Exception {
        Path bundle = bundle();
        SshClientAdapter ssh = mock(SshClientAdapter.class);
        when(ssh.execute(any()))
                .thenReturn(result(0, ""))
                .thenReturn(result(0, "RVPORT_BITCODE_TOOLCHAIN_LOCK_ACQUIRED"))
                .thenReturn(result(0, "RVPORT_BITCODE_XZ_READY"))
                .thenReturn(result(0, "RVPORT_BITCODE_TOOLCHAIN_PUBLISHED"))
                .thenReturn(result(0, ""));
        when(ssh.upload(any())).thenReturn(new SshFileTransferResult(Files.size(bundle), sha256(bundle), Duration.ZERO));

        assertThatThrownBy(() -> manager(ssh, bundle, sha256(bundle)).ensure(request()))
                .isInstanceOfSatisfying(BitcodeRuntimeException.class,
                        ex -> assertThat(ex.reasonCode()).isEqualTo(BitcodeReasonCode.TOOLCHAIN_CACHE_INVALID));
    }

    private RemoteBitcodeToolchainManager manager(SshClientAdapter ssh, Path bundle, String hash) {
        RvPortProperties.Bitcode bitcode = new RvPortProperties.Bitcode(true, "llvm-test", "21.1.8",
                bundle.toString(), hash, ".rvport/toolchains", 10, 1024L, 1024L * 1024L,
                10, 60, 60);
        return new RemoteBitcodeToolchainManager(ssh, new RvPortProperties(null, null, null, bitcode));
    }

    private BitcodeGenerationRequest request() {
        SshConnectionTarget target = new SshConnectionTarget(UUID.randomUUID(), "host", 22, "user", "/workspace",
                new SshRuntimeCredential(CredentialKind.SSH_PASSWORD, "user", "password", null, null));
        return new BitcodeGenerationRequest(UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(),
                "/workspace/source", target, null, mock(TaskExecutionContext.class));
    }

    private Path bundle() throws Exception {
        Path path = tempDir.resolve("toolchain.tar.xz");
        Files.writeString(path, "bundle");
        return path;
    }

    private String sha256(Path path) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(path)));
    }

    private SshCommandResult result(int exitCode, String stdout) {
        return new SshCommandResult(exitCode, stdout, "", Duration.ZERO);
    }
}
