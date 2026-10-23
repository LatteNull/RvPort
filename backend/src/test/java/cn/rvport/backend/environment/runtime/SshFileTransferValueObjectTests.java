package cn.rvport.backend.environment.runtime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.credential.CredentialKind;
import java.nio.file.Path;
import java.time.Duration;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class SshFileTransferValueObjectTests {

    @Test
    void appliesTimeoutDefaultsAndKeepsTransferBudget() {
        SshFileTransferRequest request = new SshFileTransferRequest(
                target(), null, Path.of("bundle"), "/remote/bundle", 10, null, null, null);

        assertThat(request.connectTimeout()).isEqualTo(Duration.ofSeconds(30));
        assertThat(request.transferTimeout()).isEqualTo(Duration.ofMinutes(30));
        assertThat(new SshFileTransferResult(10, "a".repeat(64), Duration.ofSeconds(1)).sizeBytes()).isEqualTo(10);
    }

    @Test
    void rejectsIncompleteOrUnboundedTransferRequests() {
        assertThatThrownBy(() -> new SshFileTransferRequest(
                null, null, Path.of("bundle"), "/remote/bundle", 10, null, null, null))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new SshFileTransferRequest(
                target(), null, Path.of("bundle"), " ", 10, null, null, null))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new SshFileTransferRequest(
                target(), null, Path.of("bundle"), "/remote/bundle", 0, null, null, null))
                .isInstanceOf(IllegalArgumentException.class);
    }

    private SshConnectionTarget target() {
        return new SshConnectionTarget(UUID.randomUUID(), "host", 22, "root", "/workspace",
                new SshRuntimeCredential(CredentialKind.SSH_PASSWORD, "root", "password", null, null));
    }
}
