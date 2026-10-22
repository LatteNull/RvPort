package cn.rvport.backend.credential;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.config.CredentialCryptoProperties;
import cn.rvport.backend.security.CredentialCipher;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.util.Base64;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class CredentialServiceTests {

    @Mock
    private CredentialRepository credentialRepository;

    @Test
    void encryptsCredentialPayloadAndReturnsMaskedSummary() {
        CredentialService service = service("0123456789abcdef0123456789abcdef");
        UUID projectId = UUID.randomUUID();
        UUID ownerId = UUID.randomUUID();
        CreateCredentialCommand command = new CreateCredentialCommand(
                projectId,
                ownerId,
                CredentialKind.SSH_PASSWORD,
                "rv-dev",
                "root@rv-dev",
                Map.of("password", "Secret123")
        );
        CredentialView created = credential(projectId, ownerId);
        when(credentialRepository.create(eq(command), any(), eq("local-v1"))).thenReturn(created);

        CredentialView response = service.create(command);

        assertThat(response.toSummary().maskedSummary()).isEqualTo("root@rv-dev");
        ArgumentCaptor<byte[]> payloadCaptor = ArgumentCaptor.forClass(byte[].class);
        verify(credentialRepository).create(eq(command), payloadCaptor.capture(), eq("local-v1"));
        assertThat(new String(payloadCaptor.getValue(), StandardCharsets.UTF_8))
                .doesNotContain("Secret123")
                .contains("cipherText");
    }

    @Test
    void rejectsMissingEncryptionKey() {
        CredentialService service = new CredentialService(
                credentialRepository,
                new CredentialCipher(new CredentialCryptoProperties("", "local-v1")),
                new ObjectMapper()
        );

        assertThatThrownBy(() -> service.create(new CreateCredentialCommand(
                UUID.randomUUID(),
                UUID.randomUUID(),
                CredentialKind.SSH_PASSWORD,
                "bad",
                "****",
                Map.of("password", "Secret123")
        ))).isInstanceOf(ApiException.class)
                .hasMessage("凭据加密密钥未正确配置");
    }

    @Test
    void masksShortTokenAsEdgeCase() {
        CredentialService service = service("0123456789abcdef0123456789abcdef");

        CreateCredentialCommand command = service.gitSecret(
                UUID.randomUUID(),
                UUID.randomUUID(),
                CredentialKind.GIT_TOKEN,
                "git",
                "https://example.com/repo.git",
                null,
                "abc"
        );

        assertThat(command.maskedSummary()).isEqualTo("****");
    }

    @Test
    void requireActiveRejectsMissingOrCrossProjectCredential() {
        CredentialService service = service("0123456789abcdef0123456789abcdef");
        UUID credentialId = UUID.randomUUID();
        UUID projectId = UUID.randomUUID();
        when(credentialRepository.findActiveById(credentialId)).thenReturn(java.util.Optional.empty());

        assertThatThrownBy(() -> service.requireActive(credentialId, projectId))
                .isInstanceOf(ApiException.class)
                .hasMessage("凭据不存在");

        when(credentialRepository.findActiveById(credentialId)).thenReturn(java.util.Optional.of(credential(UUID.randomUUID(), UUID.randomUUID())));

        assertThatThrownBy(() -> service.requireActive(credentialId, projectId))
                .isInstanceOf(ApiException.class)
                .hasMessage("凭据不属于当前项目");
    }

    @Test
    void rejectsMissingSecretsAndInvalidGitCredentialKind() {
        CredentialService service = service("0123456789abcdef0123456789abcdef");
        UUID projectId = UUID.randomUUID();
        UUID ownerId = UUID.randomUUID();

        assertThatThrownBy(() -> service.sshPassword(projectId, ownerId, "ssh", "host", "root", " "))
                .isInstanceOf(ApiException.class)
                .hasMessage("SSH 密码不能为空");
        assertThatThrownBy(() -> service.sshKey(projectId, ownerId, "ssh", "host", "root", "", null))
                .isInstanceOf(ApiException.class)
                .hasMessage("SSH 私钥不能为空");
        assertThatThrownBy(() -> service.gitSecret(projectId, ownerId, CredentialKind.SSH_PASSWORD, "git", "https://example.com/repo.git", null, "secret"))
                .isInstanceOf(ApiException.class)
                .hasMessage("Git 凭据类型不正确");
        assertThatThrownBy(() -> service.gitSecret(projectId, ownerId, CredentialKind.GIT_TOKEN, "git", "https://example.com/repo.git", null, " "))
                .isInstanceOf(ApiException.class)
                .hasMessage("Git 凭据不能为空");
    }

    @Test
    void masksLongTokenAndUsesDefaultCredentialNames() {
        CredentialService service = service("0123456789abcdef0123456789abcdef");
        UUID projectId = UUID.randomUUID();
        UUID ownerId = UUID.randomUUID();

        CreateCredentialCommand git = service.gitSecret(projectId, ownerId, CredentialKind.GIT_TOKEN, " ", "https://example.com/repo.git", null, "abcdef123456");
        CreateCredentialCommand sshPassword = service.sshPassword(projectId, ownerId, null, "host", "root", "Secret123");
        CreateCredentialCommand sshKey = service.sshKey(projectId, ownerId, null, "host", "root", "PRIVATE", null);

        assertThat(git.name()).isEqualTo("Git credential");
        assertThat(git.maskedSummary()).isEqualTo("****3456");
        assertThat(sshPassword.name()).isEqualTo("SSH password");
        assertThat(sshKey.name()).isEqualTo("SSH key");
    }

    @Test
    void runtimeDecryptsSshPasswordWithoutExposingSecretInStoredPayloadOrSummary() {
        CredentialService service = service("0123456789abcdef0123456789abcdef");
        UUID projectId = UUID.randomUUID();
        UUID ownerId = UUID.randomUUID();
        UUID credentialId = UUID.randomUUID();
        CredentialView created = new CredentialView(
                credentialId,
                projectId,
                ownerId,
                CredentialKind.SSH_PASSWORD,
                "ssh",
                "root@host",
                "local-v1",
                CredentialStatus.ACTIVE,
                OffsetDateTime.now(),
                null
        );
        ArgumentCaptor<byte[]> payloadCaptor = ArgumentCaptor.forClass(byte[].class);
        when(credentialRepository.create(any(), payloadCaptor.capture(), eq("local-v1"))).thenReturn(created);

        CredentialView view = service.create(service.sshPassword(projectId, ownerId, "ssh", "host", "root", "Secret123"));
        when(credentialRepository.findActiveById(credentialId)).thenReturn(java.util.Optional.of(view));
        when(credentialRepository.findActiveEncryptedById(credentialId))
                .thenReturn(java.util.Optional.of(new CredentialRepository.EncryptedCredentialRecord(CredentialKind.SSH_PASSWORD, payloadCaptor.getValue())));

        CredentialService.SshRuntimeCredential runtime = service.sshRuntimeCredential(credentialId, projectId);

        assertThat(runtime.username()).isEqualTo("root");
        assertThat(runtime.password()).isEqualTo("Secret123");
        assertThat(runtime.privateKey()).isNull();
        assertThat(view.toSummary().toString()).doesNotContain("Secret123");
        assertThat(new String(payloadCaptor.getValue(), StandardCharsets.UTF_8)).doesNotContain("Secret123");
    }

    @Test
    void runtimeDecryptsSshKeyWithPassphrase() {
        CredentialService service = service("0123456789abcdef0123456789abcdef");
        UUID projectId = UUID.randomUUID();
        UUID ownerId = UUID.randomUUID();
        UUID credentialId = UUID.randomUUID();
        CredentialView created = new CredentialView(
                credentialId,
                projectId,
                ownerId,
                CredentialKind.SSH_KEY,
                "ssh-key",
                "root@host",
                "local-v1",
                CredentialStatus.ACTIVE,
                OffsetDateTime.now(),
                null
        );
        ArgumentCaptor<byte[]> payloadCaptor = ArgumentCaptor.forClass(byte[].class);
        when(credentialRepository.create(any(), payloadCaptor.capture(), eq("local-v1"))).thenReturn(created);

        CredentialView view = service.create(service.sshKey(projectId, ownerId, "ssh-key", "host", "root", "PRIVATE_KEY", "KeyPass"));
        when(credentialRepository.findActiveById(credentialId)).thenReturn(java.util.Optional.of(view));
        when(credentialRepository.findActiveEncryptedById(credentialId))
                .thenReturn(java.util.Optional.of(new CredentialRepository.EncryptedCredentialRecord(CredentialKind.SSH_KEY, payloadCaptor.getValue())));

        CredentialService.SshRuntimeCredential runtime = service.sshRuntimeCredential(credentialId, projectId);

        assertThat(runtime.privateKey()).isEqualTo("PRIVATE_KEY");
        assertThat(runtime.passphrase()).isEqualTo("KeyPass");
        assertThat(runtime.password()).isNull();
        assertThat(new String(payloadCaptor.getValue(), StandardCharsets.UTF_8))
                .doesNotContain("PRIVATE_KEY")
                .doesNotContain("KeyPass");
    }

    @Test
    void runtimeDecryptsGitTokenAndPasswordCredentials() {
        CredentialService service = service("0123456789abcdef0123456789abcdef");
        UUID projectId = UUID.randomUUID();
        UUID ownerId = UUID.randomUUID();
        UUID tokenId = UUID.randomUUID();
        UUID passwordId = UUID.randomUUID();
        ArgumentCaptor<byte[]> payloadCaptor = ArgumentCaptor.forClass(byte[].class);
        when(credentialRepository.create(any(), payloadCaptor.capture(), eq("local-v1")))
                .thenReturn(gitCredential(tokenId, projectId, ownerId, CredentialKind.GIT_TOKEN))
                .thenReturn(gitCredential(passwordId, projectId, ownerId, CredentialKind.GIT_PASSWORD));

        CredentialView tokenView = service.create(service.gitSecret(projectId, ownerId, CredentialKind.GIT_TOKEN, "token", "https://example.com/repo.git", "", "TokenSecret"));
        byte[] tokenPayload = payloadCaptor.getAllValues().get(0);
        CredentialView passwordView = service.create(service.gitSecret(projectId, ownerId, CredentialKind.GIT_PASSWORD, "password", "https://example.com/repo.git", "git-user", "PasswordSecret"));
        byte[] passwordPayload = payloadCaptor.getAllValues().get(1);
        when(credentialRepository.findActiveById(tokenId)).thenReturn(java.util.Optional.of(tokenView));
        when(credentialRepository.findActiveEncryptedById(tokenId))
                .thenReturn(java.util.Optional.of(new CredentialRepository.EncryptedCredentialRecord(CredentialKind.GIT_TOKEN, tokenPayload)));
        when(credentialRepository.findActiveById(passwordId)).thenReturn(java.util.Optional.of(passwordView));
        when(credentialRepository.findActiveEncryptedById(passwordId))
                .thenReturn(java.util.Optional.of(new CredentialRepository.EncryptedCredentialRecord(CredentialKind.GIT_PASSWORD, passwordPayload)));

        CredentialService.GitRuntimeCredential token = service.gitRuntimeCredential(tokenId, projectId);
        CredentialService.GitRuntimeCredential password = service.gitRuntimeCredential(passwordId, projectId);

        assertThat(token.kind()).isEqualTo(CredentialKind.GIT_TOKEN);
        assertThat(token.secret()).isEqualTo("TokenSecret");
        assertThat(password.username()).isEqualTo("git-user");
        assertThat(password.secret()).isEqualTo("PasswordSecret");
        assertThat(new String(tokenPayload, StandardCharsets.UTF_8)).doesNotContain("TokenSecret");
        assertThat(new String(passwordPayload, StandardCharsets.UTF_8)).doesNotContain("PasswordSecret");
    }

    @Test
    void runtimeRejectsNonGitCredentialForGitUsage() {
        CredentialService service = service("0123456789abcdef0123456789abcdef");
        UUID projectId = UUID.randomUUID();
        UUID ownerId = UUID.randomUUID();
        UUID credentialId = UUID.randomUUID();
        CredentialView view = new CredentialView(
                credentialId,
                projectId,
                ownerId,
                CredentialKind.SSH_PASSWORD,
                "ssh",
                "root@host",
                "local-v1",
                CredentialStatus.ACTIVE,
                OffsetDateTime.now(),
                null
        );
        when(credentialRepository.findActiveById(credentialId)).thenReturn(java.util.Optional.of(view));
        when(credentialRepository.findActiveEncryptedById(credentialId))
                .thenReturn(java.util.Optional.of(new CredentialRepository.EncryptedCredentialRecord(CredentialKind.SSH_PASSWORD, "{}".getBytes(StandardCharsets.UTF_8))));

        assertThatThrownBy(() -> service.gitRuntimeCredential(credentialId, projectId))
                .isInstanceOf(ApiException.class)
                .hasMessage("Git 凭据类型不正确");
    }

    @Test
    void validatesRequiredCreateFieldsIndependently() {
        CredentialService service = service("0123456789abcdef0123456789abcdef");
        UUID projectId = UUID.randomUUID();
        UUID ownerId = UUID.randomUUID();

        assertThatThrownBy(() -> service.create(new CreateCredentialCommand(
                null, ownerId, CredentialKind.SSH_PASSWORD, "name", "masked", Map.of())))
                .isInstanceOf(ApiException.class).hasMessage("凭据项目和所有者不能为空");
        assertThatThrownBy(() -> service.create(new CreateCredentialCommand(
                projectId, null, CredentialKind.SSH_PASSWORD, "name", "masked", Map.of())))
                .isInstanceOf(ApiException.class).hasMessage("凭据项目和所有者不能为空");
        assertThatThrownBy(() -> service.create(new CreateCredentialCommand(
                projectId, ownerId, null, "name", "masked", Map.of())))
                .isInstanceOf(ApiException.class).hasMessage("凭据类型和名称不能为空");
        assertThatThrownBy(() -> service.create(new CreateCredentialCommand(
                projectId, ownerId, CredentialKind.SSH_PASSWORD, null, "masked", Map.of())))
                .isInstanceOf(ApiException.class).hasMessage("凭据类型和名称不能为空");
        assertThatThrownBy(() -> service.create(new CreateCredentialCommand(
                projectId, ownerId, CredentialKind.SSH_PASSWORD, " ", "masked", Map.of())))
                .isInstanceOf(ApiException.class).hasMessage("凭据类型和名称不能为空");
    }

    @Test
    void rejectsNullSecretsAsEdgeCases() {
        CredentialService service = service("0123456789abcdef0123456789abcdef");
        UUID projectId = UUID.randomUUID();
        UUID ownerId = UUID.randomUUID();

        assertThatThrownBy(() -> service.sshPassword(projectId, ownerId, "ssh", "host", "root", null))
                .isInstanceOf(ApiException.class).hasMessage("SSH 密码不能为空");
        assertThatThrownBy(() -> service.sshKey(projectId, ownerId, "ssh", "host", "root", null, null))
                .isInstanceOf(ApiException.class).hasMessage("SSH 私钥不能为空");
        assertThatThrownBy(() -> service.gitSecret(
                projectId, ownerId, CredentialKind.GIT_TOKEN, "git", "url", null, null))
                .isInstanceOf(ApiException.class).hasMessage("Git 凭据不能为空");
    }

    @Test
    void runtimeRejectsMissingEncryptedRecordsWrongKindsAndMalformedPayloads() {
        CredentialService service = service("0123456789abcdef0123456789abcdef");
        UUID projectId = UUID.randomUUID();
        UUID ownerId = UUID.randomUUID();
        UUID id = UUID.randomUUID();
        CredentialView ssh = new CredentialView(id, projectId, ownerId, CredentialKind.SSH_PASSWORD,
                "ssh", "root@host", "local-v1", CredentialStatus.ACTIVE, OffsetDateTime.now(), null);
        when(credentialRepository.findActiveById(id)).thenReturn(Optional.of(ssh));
        when(credentialRepository.findActiveEncryptedById(id)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.sshRuntimeCredential(id, projectId))
                .isInstanceOf(ApiException.class).hasMessage("凭据不存在");
        assertThatThrownBy(() -> service.gitRuntimeCredential(id, projectId))
                .isInstanceOf(ApiException.class).hasMessage("凭据不存在");

        when(credentialRepository.findActiveEncryptedById(id)).thenReturn(Optional.of(
                new CredentialRepository.EncryptedCredentialRecord(CredentialKind.GIT_TOKEN, new byte[] {1})));
        assertThatThrownBy(() -> service.sshRuntimeCredential(id, projectId))
                .isInstanceOf(ApiException.class).hasMessage("SSH 凭据类型不正确");

        when(credentialRepository.findActiveEncryptedById(id)).thenReturn(Optional.of(
                new CredentialRepository.EncryptedCredentialRecord(CredentialKind.SSH_PASSWORD,
                        "not-json".getBytes(StandardCharsets.UTF_8))));
        assertThatThrownBy(() -> service.sshRuntimeCredential(id, projectId))
                .isInstanceOf(ApiException.class).hasMessage("SSH 凭据无法解密");
    }

    @Test
    void runtimeRejectsMalformedGitPayloadAndNullProjectOwnership() {
        CredentialService service = service("0123456789abcdef0123456789abcdef");
        UUID projectId = UUID.randomUUID();
        UUID ownerId = UUID.randomUUID();
        UUID id = UUID.randomUUID();
        CredentialView noProject = new CredentialView(id, null, ownerId, CredentialKind.GIT_TOKEN,
                "git", "****", "local-v1", CredentialStatus.ACTIVE, OffsetDateTime.now(), null);
        when(credentialRepository.findActiveById(id)).thenReturn(Optional.of(noProject));
        assertThatThrownBy(() -> service.requireActive(id, projectId))
                .isInstanceOf(ApiException.class).hasMessage("凭据不属于当前项目");

        CredentialView git = gitCredential(id, projectId, ownerId, CredentialKind.GIT_TOKEN);
        when(credentialRepository.findActiveById(id)).thenReturn(Optional.of(git));
        when(credentialRepository.findActiveEncryptedById(id)).thenReturn(Optional.of(
                new CredentialRepository.EncryptedCredentialRecord(CredentialKind.GIT_TOKEN,
                        "not-json".getBytes(StandardCharsets.UTF_8))));
        assertThatThrownBy(() -> service.gitRuntimeCredential(id, projectId))
                .isInstanceOf(ApiException.class).hasMessage("Git 凭据无法解密");
    }

    @Test
    void createsRuntimeCredentialWithMissingOptionalPayloadValues() {
        CredentialService service = service("0123456789abcdef0123456789abcdef");
        UUID projectId = UUID.randomUUID();
        UUID ownerId = UUID.randomUUID();
        UUID id = UUID.randomUUID();
        ArgumentCaptor<byte[]> payloadCaptor = ArgumentCaptor.forClass(byte[].class);
        CredentialView view = new CredentialView(id, projectId, ownerId, CredentialKind.SSH_PASSWORD,
                "ssh", "root@host", "local-v1", CredentialStatus.ACTIVE, OffsetDateTime.now(), null);
        when(credentialRepository.create(any(), payloadCaptor.capture(), eq("local-v1"))).thenReturn(view);
        CredentialView created = service.create(new CreateCredentialCommand(projectId, ownerId,
                CredentialKind.SSH_PASSWORD, "ssh", "root@host", Map.of()));
        when(credentialRepository.findActiveById(id)).thenReturn(Optional.of(created));
        when(credentialRepository.findActiveEncryptedById(id)).thenReturn(Optional.of(
                new CredentialRepository.EncryptedCredentialRecord(CredentialKind.SSH_PASSWORD,
                        payloadCaptor.getValue())));

        CredentialService.SshRuntimeCredential runtime = service.sshRuntimeCredential(id, projectId);
        assertThat(runtime.username()).isEmpty();
        assertThat(runtime.password()).isEmpty();
        assertThat(CredentialSummaryResponse.empty().configured()).isFalse();
    }

    private CredentialService service(String rawKey) {
        String key = Base64.getEncoder().encodeToString(rawKey.getBytes(StandardCharsets.UTF_8));
        return new CredentialService(
                credentialRepository,
                new CredentialCipher(new CredentialCryptoProperties(key, "local-v1")),
                new ObjectMapper()
        );
    }

    private CredentialView credential(UUID projectId, UUID ownerId) {
        return new CredentialView(
                UUID.randomUUID(),
                projectId,
                ownerId,
                CredentialKind.SSH_PASSWORD,
                "rv-dev",
                "root@rv-dev",
                "local-v1",
                CredentialStatus.ACTIVE,
                OffsetDateTime.now(),
                null
        );
    }

    private CredentialView gitCredential(UUID credentialId, UUID projectId, UUID ownerId, CredentialKind kind) {
        return new CredentialView(
                credentialId,
                projectId,
                ownerId,
                kind,
                "git",
                "****",
                "local-v1",
                CredentialStatus.ACTIVE,
                OffsetDateTime.now(),
                null
        );
    }
}
