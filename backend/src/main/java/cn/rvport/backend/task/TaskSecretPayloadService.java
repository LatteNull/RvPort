package cn.rvport.backend.task;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.credential.CredentialKind;
import cn.rvport.backend.security.CredentialCipher;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import org.jooq.JSONB;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class TaskSecretPayloadService {

    public static final String SSH_PRECHECK_CREDENTIAL = "SSH_PRECHECK_CREDENTIAL";

    private final TaskSecretPayloadRepository repository;
    private final CredentialCipher credentialCipher;
    private final ObjectMapper objectMapper;

    public TaskSecretPayloadService(
            TaskSecretPayloadRepository repository,
            CredentialCipher credentialCipher,
            ObjectMapper objectMapper
    ) {
        this.repository = repository;
        this.credentialCipher = credentialCipher;
        this.objectMapper = objectMapper;
    }

    public PreparedSecret prepareSshPrecheckCredential(
            CredentialKind kind,
            String username,
            String password,
            String privateKey,
            String passphrase
    ) {
        if (kind == CredentialKind.SSH_PASSWORD && (password == null || password.isBlank())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "CREDENTIAL_SECRET_REQUIRED", "SSH 密码不能为空");
        }
        if (kind == CredentialKind.SSH_KEY && (privateKey == null || privateKey.isBlank())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "CREDENTIAL_SECRET_REQUIRED", "SSH 私钥不能为空");
        }
        if (kind != CredentialKind.SSH_PASSWORD && kind != CredentialKind.SSH_KEY) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "CREDENTIAL_KIND_INVALID", "SSH 凭据类型不支持");
        }

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("kind", kind.name());
        payload.put("username", username);
        if (kind == CredentialKind.SSH_PASSWORD) {
            payload.put("password", password);
        } else {
            payload.put("privateKey", privateKey);
            if (passphrase != null && !passphrase.isBlank()) {
                payload.put("passphrase", passphrase);
            }
        }

        try {
            byte[] plainPayload = objectMapper.writeValueAsBytes(payload);
            String sha256 = sha256(plainPayload);
            CredentialCipher.EncryptedSecret encrypted = credentialCipher.encrypt(plainPayload);
            return new PreparedSecret(
                    UUID.randomUUID(),
                    SSH_PRECHECK_CREDENTIAL,
                    sha256,
                    JSONB.valueOf(objectMapper.writeValueAsString(encrypted)),
                    encrypted.keyId()
            );
        } catch (JsonProcessingException ex) {
            throw new ApiException(HttpStatus.INTERNAL_SERVER_ERROR, "TASK_SECRET_PAYLOAD_ENCRYPT_FAILED", "临时凭据加密结果无法序列化");
        } catch (IllegalStateException ex) {
            throw new ApiException(HttpStatus.INTERNAL_SERVER_ERROR, "TASK_SECRET_PAYLOAD_ENCRYPT_FAILED", "临时凭据加密失败");
        }
    }

    @Transactional
    public TaskSecretPayloadView save(PreparedSecret prepared, UUID projectId, UUID taskId, UUID createdBy) {
        if (prepared == null || projectId == null || taskId == null) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "TASK_SECRET_PAYLOAD_REFERENCE_INVALID", "临时凭据引用不完整");
        }
        return repository.create(
                prepared.id(),
                projectId,
                taskId,
                prepared.secretType(),
                prepared.secretSha256(),
                prepared.encryptedPayload(),
                prepared.keyId(),
                createdBy
        );
    }

    @Transactional(readOnly = true)
    public SshPrecheckCredential requireSshPrecheckCredential(UUID payloadId, UUID projectId, UUID taskId, String expectedSha256) {
        TaskSecretPayloadView payload = repository.findByIdAndTask(payloadId, projectId, taskId, SSH_PRECHECK_CREDENTIAL)
                .orElseThrow(() -> new TaskExecutionException(TaskErrorCode.RESOURCE_NOT_FOUND, "临时凭据引用不存在", null));
        try {
            CredentialCipher.EncryptedSecret encrypted = objectMapper.readValue(
                    payload.encryptedPayload().data(),
                    CredentialCipher.EncryptedSecret.class
            );
            byte[] plainPayload = credentialCipher.decrypt(encrypted);
            String actualSha256 = sha256(plainPayload);
            if (expectedSha256 != null && !expectedSha256.isBlank() && !actualSha256.equals(expectedSha256)) {
                throw new TaskExecutionException(TaskErrorCode.INPUT_INVALID, "临时凭据 hash 校验失败", null);
            }
            Map<?, ?> value = objectMapper.readValue(plainPayload, Map.class);
            CredentialKind kind = CredentialKind.valueOf(stringValue(value.get("kind")));
            return new SshPrecheckCredential(
                    kind,
                    stringValue(value.get("username")),
                    stringValue(value.get("password")),
                    stringValue(value.get("privateKey")),
                    stringValue(value.get("passphrase"))
            );
        } catch (IOException | IllegalArgumentException | IllegalStateException ex) {
            throw new TaskExecutionException(TaskErrorCode.CREDENTIAL_DECRYPT_FAILED, "临时凭据无法解密", ex);
        }
    }

    @Transactional
    public int deleteByTaskId(UUID taskId) {
        if (taskId == null) {
            return 0;
        }
        return repository.deleteByTaskId(taskId);
    }

    private String stringValue(Object value) {
        return value == null ? null : value.toString();
    }

    private String sha256(byte[] bytes) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException(ex);
        }
    }

    public record PreparedSecret(
            UUID id,
            String secretType,
            String secretSha256,
            JSONB encryptedPayload,
            String keyId
    ) {
    }

    public record SshPrecheckCredential(
            CredentialKind kind,
            String username,
            String password,
            String privateKey,
            String passphrase
    ) {
    }
}
