package cn.rvport.backend.task;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.security.CredentialCipher;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.core.JsonProcessingException;
import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.util.Optional;
import java.util.UUID;
import org.jooq.JSONB;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class TaskScriptPayloadServiceTests {

    @Mock
    private TaskScriptPayloadRepository repository;

    @Mock
    private CredentialCipher credentialCipher;

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    void savesEncryptedPayloadWithHashAndLength() {
        TaskScriptPayloadService service = service();
        UUID payloadId = UUID.randomUUID();
        UUID projectId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        when(credentialCipher.encrypt("echo ok".getBytes(StandardCharsets.UTF_8)))
                .thenReturn(new CredentialCipher.EncryptedSecret("AES-256-GCM", "local-v1", "iv", "cipher"));
        when(repository.create(eq(payloadId), eq(projectId), eq(taskId), any(), eq(7), any(), eq("local-v1"), eq(actorId)))
                .thenAnswer(invocation -> new TaskScriptPayloadView(
                        payloadId,
                        projectId,
                        taskId,
                        invocation.getArgument(3),
                        7,
                        invocation.getArgument(5),
                        "local-v1",
                        actorId,
                        OffsetDateTime.now()
                ));

        TaskScriptPayloadView saved = service.save(payloadId, projectId, taskId, "echo ok", actorId);

        assertThat(saved.scriptSha256()).hasSize(64);
        assertThat(saved.encryptedPayload().data()).contains("cipher").doesNotContain("echo ok");
    }

    @Test
    void rejectsMissingScriptBeforeEncrypting() {
        TaskScriptPayloadService service = service();

        assertThatThrownBy(() -> service.save(UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), " ", UUID.randomUUID()))
                .isInstanceOf(ApiException.class)
                .hasMessage("自定义脚本不能为空");

        verify(credentialCipher, never()).encrypt(any());
    }

    @Test
    void readsAndValidatesHash() throws Exception {
        TaskScriptPayloadService service = service();
        UUID payloadId = UUID.randomUUID();
        UUID projectId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        String script = "printf 'ok\\n'";
        String encryptedJson = objectMapper.writeValueAsString(new CredentialCipher.EncryptedSecret("AES-256-GCM", "local-v1", "iv", "cipher"));
        when(repository.findByIdAndTask(payloadId, projectId, taskId))
                .thenReturn(Optional.of(new TaskScriptPayloadView(
                        payloadId, projectId, taskId, "sha", script.length(), JSONB.valueOf(encryptedJson),
                        "local-v1", UUID.randomUUID(), OffsetDateTime.now())));
        when(credentialCipher.decrypt(any())).thenReturn(script.getBytes(StandardCharsets.UTF_8));

        String loaded = service.requireScript(payloadId, projectId, taskId, sha256(script));

        assertThat(loaded).isEqualTo(script);
    }

    @Test
    void rejectsMissingPayloadAndHashMismatch() throws Exception {
        TaskScriptPayloadService service = service();
        UUID payloadId = UUID.randomUUID();
        UUID projectId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        when(repository.findByIdAndTask(payloadId, projectId, taskId)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.requireScript(payloadId, projectId, taskId, "abc"))
                .isInstanceOf(TaskExecutionException.class)
                .hasMessage("脚本正文引用不存在");

        String encryptedJson = objectMapper.writeValueAsString(new CredentialCipher.EncryptedSecret("AES-256-GCM", "local-v1", "iv", "cipher"));
        when(repository.findByIdAndTask(payloadId, projectId, taskId))
                .thenReturn(Optional.of(new TaskScriptPayloadView(
                        payloadId, projectId, taskId, "sha", 4, JSONB.valueOf(encryptedJson),
                        "local-v1", UUID.randomUUID(), OffsetDateTime.now())));
        when(credentialCipher.decrypt(any())).thenReturn("echo".getBytes(StandardCharsets.UTF_8));

        assertThatThrownBy(() -> service.requireScript(payloadId, projectId, taskId, "0000"))
                .isInstanceOf(TaskExecutionException.class)
                .hasMessage("脚本正文 hash 校验失败");
    }

    @Test
    void rejectsEveryIncompletePayloadReference() {
        TaskScriptPayloadService service = service();
        UUID id = UUID.randomUUID();
        for (UUID[] references : new UUID[][]{
                {null, id, id}, {id, null, id}, {id, id, null}}) {
            assertThatThrownBy(() -> service.save(
                    references[0], references[1], references[2], "echo ok", id))
                    .isInstanceOf(ApiException.class)
                    .hasMessage("脚本引用不完整");
        }
        verify(credentialCipher, never()).encrypt(any());
    }

    @Test
    void acceptsMissingExpectedHashAndMapsDecryptFailure() throws Exception {
        UUID payloadId = UUID.randomUUID();
        UUID projectId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        String encryptedJson = objectMapper.writeValueAsString(
                new CredentialCipher.EncryptedSecret("AES-256-GCM", "local-v1", "iv", "cipher"));
        TaskScriptPayloadView payload = new TaskScriptPayloadView(
                payloadId, projectId, taskId, "sha", 4, JSONB.valueOf(encryptedJson),
                "local-v1", UUID.randomUUID(), OffsetDateTime.now());
        when(repository.findByIdAndTask(payloadId, projectId, taskId)).thenReturn(Optional.of(payload));
        when(credentialCipher.decrypt(any())).thenReturn("echo".getBytes(StandardCharsets.UTF_8));
        assertThat(service().requireScript(payloadId, projectId, taskId, null)).isEqualTo("echo");
        assertThat(service().requireScript(payloadId, projectId, taskId, " ")).isEqualTo("echo");

        when(credentialCipher.decrypt(any())).thenThrow(new IllegalStateException("decrypt failed"));
        assertThatThrownBy(() -> service().requireScript(payloadId, projectId, taskId, null))
                .isInstanceOf(TaskExecutionException.class)
                .hasMessage("脚本正文无法解密");
    }

    @Test
    void mapsEncryptionAndSerializationFailures() {
        UUID id = UUID.randomUUID();
        when(credentialCipher.encrypt(any())).thenThrow(new IllegalStateException("encrypt failed"));
        assertThatThrownBy(() -> service().save(id, id, id, "echo", id))
                .isInstanceOf(ApiException.class)
                .hasMessage("脚本正文加密失败");

        CredentialCipher cipher = org.mockito.Mockito.mock(CredentialCipher.class);
        when(cipher.encrypt(any())).thenReturn(
                new CredentialCipher.EncryptedSecret("AES", "key", "iv", "cipher"));
        ObjectMapper failingMapper = new ObjectMapper() {
            @Override
            public String writeValueAsString(Object value) throws JsonProcessingException {
                throw new JsonProcessingException("broken") {
                };
            }
        };
        TaskScriptPayloadService failing = new TaskScriptPayloadService(repository, cipher, failingMapper);
        assertThatThrownBy(() -> failing.save(id, id, id, "echo", id))
                .isInstanceOf(ApiException.class)
                .hasMessage("脚本正文加密结果无法序列化");
    }

    private TaskScriptPayloadService service() {
        return new TaskScriptPayloadService(repository, credentialCipher, objectMapper);
    }

    private String sha256(String value) {
        try {
            return java.util.HexFormat.of().formatHex(
                    java.security.MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8)));
        } catch (java.security.NoSuchAlgorithmException ex) {
            throw new IllegalStateException(ex);
        }
    }
}
