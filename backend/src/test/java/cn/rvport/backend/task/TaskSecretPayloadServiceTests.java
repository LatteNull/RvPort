package cn.rvport.backend.task;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.credential.CredentialKind;
import cn.rvport.backend.security.CredentialCipher;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.OffsetDateTime;
import java.util.HexFormat;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.jooq.JSONB;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpStatus;

@ExtendWith(MockitoExtension.class)
class TaskSecretPayloadServiceTests {

    @Mock private TaskSecretPayloadRepository repository;
    @Mock private CredentialCipher credentialCipher;
    private ObjectMapper objectMapper;
    private TaskSecretPayloadService service;

    @BeforeEach
    void setUp() {
        objectMapper = new ObjectMapper();
        service = new TaskSecretPayloadService(repository, credentialCipher, objectMapper);
    }

    @Test
    void preparesPasswordAndKeyCredentialsWithoutPersistingThem() {
        CredentialCipher.EncryptedSecret encrypted = encrypted();
        when(credentialCipher.encrypt(any(byte[].class))).thenReturn(encrypted);

        var password = service.prepareSshPrecheckCredential(
                CredentialKind.SSH_PASSWORD, "root", "password", null, null);
        var key = service.prepareSshPrecheckCredential(
                CredentialKind.SSH_KEY, "root", null, "private-key", "passphrase");
        var keyWithoutPassphrase = service.prepareSshPrecheckCredential(
                CredentialKind.SSH_KEY, "root", null, "private-key", " ");
        var keyWithNullPassphrase = service.prepareSshPrecheckCredential(
                CredentialKind.SSH_KEY, "root", null, "private-key", null);

        assertThat(password.secretType()).isEqualTo(TaskSecretPayloadService.SSH_PRECHECK_CREDENTIAL);
        assertThat(password.secretSha256()).hasSize(64);
        assertThat(password.encryptedPayload().data()).doesNotContain("password");
        assertThat(key.keyId()).isEqualTo("key-v1");
        assertThat(keyWithoutPassphrase.encryptedPayload()).isNotNull();
        assertThat(keyWithNullPassphrase.encryptedPayload()).isNotNull();
        org.mockito.Mockito.verifyNoInteractions(repository);
    }

    @Test
    void validatesRequiredSecretsAndCredentialKind() {
        assertApi(() -> service.prepareSshPrecheckCredential(CredentialKind.SSH_PASSWORD, "root", " ", null, null),
                "CREDENTIAL_SECRET_REQUIRED");
        assertApi(() -> service.prepareSshPrecheckCredential(CredentialKind.SSH_PASSWORD, "root", null, null, null),
                "CREDENTIAL_SECRET_REQUIRED");
        assertApi(() -> service.prepareSshPrecheckCredential(CredentialKind.SSH_KEY, "root", null, null, null),
                "CREDENTIAL_SECRET_REQUIRED");
        assertApi(() -> service.prepareSshPrecheckCredential(CredentialKind.SSH_KEY, "root", null, " ", null),
                "CREDENTIAL_SECRET_REQUIRED");
        assertApi(() -> service.prepareSshPrecheckCredential(CredentialKind.GIT_TOKEN, "root", null, null, null),
                "CREDENTIAL_KIND_INVALID");
    }

    @Test
    void mapsEncryptionAndSerializationFailures() throws Exception {
        when(credentialCipher.encrypt(any(byte[].class))).thenThrow(new IllegalStateException("no key"));
        assertApi(() -> service.prepareSshPrecheckCredential(
                CredentialKind.SSH_PASSWORD, "root", "password", null, null),
                "TASK_SECRET_PAYLOAD_ENCRYPT_FAILED");

        ObjectMapper broken = org.mockito.Mockito.mock(ObjectMapper.class);
        when(broken.writeValueAsBytes(any())).thenThrow(new com.fasterxml.jackson.core.JsonProcessingException("bad") { });
        TaskSecretPayloadService brokenService = new TaskSecretPayloadService(repository, credentialCipher, broken);
        assertApi(() -> brokenService.prepareSshPrecheckCredential(
                CredentialKind.SSH_PASSWORD, "root", "password", null, null),
                "TASK_SECRET_PAYLOAD_ENCRYPT_FAILED");
    }

    @Test
    void savesPreparedPayloadAndRejectsIncompleteReference() {
        UUID projectId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        TaskSecretPayloadService.PreparedSecret prepared = new TaskSecretPayloadService.PreparedSecret(
                UUID.randomUUID(), TaskSecretPayloadService.SSH_PRECHECK_CREDENTIAL, "sha", JSONB.valueOf("{}"), "key-v1");
        TaskSecretPayloadView created = view(prepared, projectId, taskId);
        when(repository.create(prepared.id(), projectId, taskId, prepared.secretType(), prepared.secretSha256(),
                prepared.encryptedPayload(), prepared.keyId(), actorId)).thenReturn(created);

        assertThat(service.save(prepared, projectId, taskId, actorId)).isEqualTo(created);
        assertApi(() -> service.save(null, projectId, taskId, actorId), "TASK_SECRET_PAYLOAD_REFERENCE_INVALID");
        assertApi(() -> service.save(prepared, null, taskId, actorId), "TASK_SECRET_PAYLOAD_REFERENCE_INVALID");
        assertApi(() -> service.save(prepared, projectId, null, actorId), "TASK_SECRET_PAYLOAD_REFERENCE_INVALID");
    }

    @Test
    void decryptsAndValidatesPasswordCredentialHash() throws Exception {
        UUID projectId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        UUID payloadId = UUID.randomUUID();
        byte[] plain = objectMapper.writeValueAsBytes(Map.of(
                "kind", "SSH_PASSWORD", "username", "root", "password", "secret"));
        CredentialCipher.EncryptedSecret encrypted = encrypted();
        TaskSecretPayloadService.PreparedSecret prepared = new TaskSecretPayloadService.PreparedSecret(
                payloadId, TaskSecretPayloadService.SSH_PRECHECK_CREDENTIAL, sha256(plain),
                JSONB.valueOf(objectMapper.writeValueAsString(encrypted)), encrypted.keyId());
        when(repository.findByIdAndTask(payloadId, projectId, taskId, TaskSecretPayloadService.SSH_PRECHECK_CREDENTIAL))
                .thenReturn(Optional.of(view(prepared, projectId, taskId)));
        when(credentialCipher.decrypt(encrypted)).thenReturn(plain);

        var credential = service.requireSshPrecheckCredential(payloadId, projectId, taskId, sha256(plain));

        assertThat(credential.kind()).isEqualTo(CredentialKind.SSH_PASSWORD);
        assertThat(credential.username()).isEqualTo("root");
        assertThat(credential.password()).isEqualTo("secret");
        assertThat(credential.privateKey()).isNull();
    }

    @Test
    void mapsMissingHashMismatchAndMalformedPayloads() throws Exception {
        UUID projectId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        UUID payloadId = UUID.randomUUID();
        when(repository.findByIdAndTask(payloadId, projectId, taskId, TaskSecretPayloadService.SSH_PRECHECK_CREDENTIAL))
                .thenReturn(Optional.empty());
        assertThatThrownBy(() -> service.requireSshPrecheckCredential(payloadId, projectId, taskId, null))
                .isInstanceOfSatisfying(TaskExecutionException.class, ex ->
                        assertThat(ex.errorCode()).isEqualTo(TaskErrorCode.RESOURCE_NOT_FOUND));

        CredentialCipher.EncryptedSecret encrypted = encrypted();
        byte[] plain = "{\"kind\":\"SSH_KEY\",\"privateKey\":\"key\"}".getBytes(StandardCharsets.UTF_8);
        TaskSecretPayloadService.PreparedSecret prepared = new TaskSecretPayloadService.PreparedSecret(
                payloadId, TaskSecretPayloadService.SSH_PRECHECK_CREDENTIAL, sha256(plain),
                JSONB.valueOf(objectMapper.writeValueAsString(encrypted)), encrypted.keyId());
        when(repository.findByIdAndTask(payloadId, projectId, taskId, TaskSecretPayloadService.SSH_PRECHECK_CREDENTIAL))
                .thenReturn(Optional.of(view(prepared, projectId, taskId)));
        when(credentialCipher.decrypt(encrypted)).thenReturn(plain);
        assertThatThrownBy(() -> service.requireSshPrecheckCredential(payloadId, projectId, taskId, "wrong"))
                .isInstanceOfSatisfying(TaskExecutionException.class, ex ->
                        assertThat(ex.errorCode()).isEqualTo(TaskErrorCode.INPUT_INVALID));

        TaskSecretPayloadService.PreparedSecret malformed = new TaskSecretPayloadService.PreparedSecret(
                payloadId, TaskSecretPayloadService.SSH_PRECHECK_CREDENTIAL, "sha", JSONB.valueOf("not-json"), "key");
        when(repository.findByIdAndTask(payloadId, projectId, taskId, TaskSecretPayloadService.SSH_PRECHECK_CREDENTIAL))
                .thenReturn(Optional.of(view(malformed, projectId, taskId)));
        assertThatThrownBy(() -> service.requireSshPrecheckCredential(payloadId, projectId, taskId, null))
                .isInstanceOfSatisfying(TaskExecutionException.class, ex ->
                        assertThat(ex.errorCode()).isEqualTo(TaskErrorCode.CREDENTIAL_DECRYPT_FAILED));
    }

    @Test
    void deletesOnlyWhenTaskIdIsPresent() {
        UUID taskId = UUID.randomUUID();
        when(repository.deleteByTaskId(taskId)).thenReturn(2);
        assertThat(service.deleteByTaskId(null)).isZero();
        assertThat(service.deleteByTaskId(taskId)).isEqualTo(2);
        verify(repository).deleteByTaskId(taskId);
    }

    private void assertApi(org.assertj.core.api.ThrowableAssert.ThrowingCallable action, String code) {
        assertThatThrownBy(action).isInstanceOfSatisfying(ApiException.class, ex -> {
            assertThat(ex.status()).isIn(HttpStatus.BAD_REQUEST, HttpStatus.INTERNAL_SERVER_ERROR);
            assertThat(ex.code()).isEqualTo(code);
        });
    }

    private CredentialCipher.EncryptedSecret encrypted() {
        return new CredentialCipher.EncryptedSecret("AES-256-GCM", "key-v1", "iv", "cipher");
    }

    private TaskSecretPayloadView view(
            TaskSecretPayloadService.PreparedSecret prepared, UUID projectId, UUID taskId
    ) {
        return new TaskSecretPayloadView(
                prepared.id(), projectId, taskId, prepared.secretType(), prepared.secretSha256(),
                prepared.encryptedPayload(), prepared.keyId(), UUID.randomUUID(), OffsetDateTime.now());
    }

    private String sha256(byte[] value) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value));
    }
}
