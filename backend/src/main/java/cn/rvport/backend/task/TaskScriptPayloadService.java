package cn.rvport.backend.task;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.security.CredentialCipher;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.UUID;
import org.jooq.JSONB;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class TaskScriptPayloadService {

    private final TaskScriptPayloadRepository repository;
    private final CredentialCipher credentialCipher;
    private final ObjectMapper objectMapper;

    public TaskScriptPayloadService(
            TaskScriptPayloadRepository repository,
            CredentialCipher credentialCipher,
            ObjectMapper objectMapper
    ) {
        this.repository = repository;
        this.credentialCipher = credentialCipher;
        this.objectMapper = objectMapper;
    }

    @Transactional
    public TaskScriptPayloadView save(
            UUID payloadId,
            UUID projectId,
            UUID taskId,
            String script,
            UUID createdBy
    ) {
        if (payloadId == null || projectId == null || taskId == null) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "SCRIPT_PAYLOAD_REFERENCE_INVALID", "脚本引用不完整");
        }
        if (script == null || script.isBlank()) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "SCRIPT_REQUIRED", "自定义脚本不能为空");
        }
        byte[] plainText = script.getBytes(StandardCharsets.UTF_8);
        try {
            CredentialCipher.EncryptedSecret encrypted = credentialCipher.encrypt(plainText);
            return repository.create(
                    payloadId,
                    projectId,
                    taskId,
                    sha256(plainText),
                    script.length(),
                    JSONB.valueOf(objectMapper.writeValueAsString(encrypted)),
                    encrypted.keyId(),
                    createdBy
            );
        } catch (JsonProcessingException ex) {
            throw new ApiException(HttpStatus.INTERNAL_SERVER_ERROR, "SCRIPT_PAYLOAD_ENCRYPT_FAILED", "脚本正文加密结果无法序列化");
        } catch (IllegalStateException ex) {
            throw new ApiException(HttpStatus.INTERNAL_SERVER_ERROR, "SCRIPT_PAYLOAD_ENCRYPT_FAILED", "脚本正文加密失败");
        }
    }

    @Transactional(readOnly = true)
    public String requireScript(UUID payloadId, UUID projectId, UUID taskId, String expectedSha256) {
        TaskScriptPayloadView payload = repository.findByIdAndTask(payloadId, projectId, taskId)
                .orElseThrow(() -> new TaskExecutionException(TaskErrorCode.RESOURCE_NOT_FOUND, "脚本正文引用不存在", null));
        try {
            CredentialCipher.EncryptedSecret encrypted = objectMapper.readValue(
                    payload.encryptedPayload().data(),
                    CredentialCipher.EncryptedSecret.class
            );
            byte[] plainText = credentialCipher.decrypt(encrypted);
            String actualSha256 = sha256(plainText);
            if (expectedSha256 != null && !expectedSha256.isBlank() && !actualSha256.equals(expectedSha256)) {
                throw new TaskExecutionException(TaskErrorCode.INPUT_INVALID, "脚本正文 hash 校验失败", null);
            }
            return new String(plainText, StandardCharsets.UTF_8);
        } catch (IOException | IllegalStateException ex) {
            throw new TaskExecutionException(TaskErrorCode.CREDENTIAL_DECRYPT_FAILED, "脚本正文无法解密", ex);
        }
    }

    private String sha256(byte[] bytes) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException(ex);
        }
    }
}
