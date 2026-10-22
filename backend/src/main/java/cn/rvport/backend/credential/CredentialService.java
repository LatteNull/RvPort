package cn.rvport.backend.credential;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.security.CredentialCipher;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class CredentialService {

    private final CredentialRepository credentialRepository;
    private final CredentialCipher credentialCipher;
    private final ObjectMapper objectMapper;

    public CredentialService(
            CredentialRepository credentialRepository,
            CredentialCipher credentialCipher,
            ObjectMapper objectMapper
    ) {
        this.credentialRepository = credentialRepository;
        this.credentialCipher = credentialCipher;
        this.objectMapper = objectMapper;
    }

    @Transactional
    public CredentialView create(CreateCredentialCommand command) {
        validate(command);
        try {
            byte[] plainPayload = objectMapper.writeValueAsBytes(command.payload());
            CredentialCipher.EncryptedSecret encrypted = credentialCipher.encrypt(plainPayload);
            byte[] storedPayload = objectMapper.writeValueAsBytes(encrypted);
            return credentialRepository.create(command, storedPayload, encrypted.keyId());
        } catch (JsonProcessingException ex) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "CREDENTIAL_PAYLOAD_INVALID", "凭据载荷无法序列化");
        } catch (IllegalStateException ex) {
            throw new ApiException(HttpStatus.INTERNAL_SERVER_ERROR, "CREDENTIAL_KEY_INVALID", "凭据加密密钥未正确配置");
        }
    }

    public CredentialView requireActive(UUID credentialId, UUID projectId) {
        CredentialView view = credentialRepository.findActiveById(credentialId)
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "CREDENTIAL_NOT_FOUND", "凭据不存在"));
        if (view.projectId() == null || !view.projectId().equals(projectId)) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "CREDENTIAL_PROJECT_MISMATCH", "凭据不属于当前项目");
        }
        return view;
    }

    public SshRuntimeCredential sshRuntimeCredential(UUID credentialId, UUID projectId) {
        CredentialView view = requireActive(credentialId, projectId);
        CredentialRepository.EncryptedCredentialRecord encrypted = credentialRepository.findActiveEncryptedById(credentialId)
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "CREDENTIAL_NOT_FOUND", "凭据不存在"));
        if (encrypted.kind() != CredentialKind.SSH_PASSWORD && encrypted.kind() != CredentialKind.SSH_KEY) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "CREDENTIAL_KIND_INVALID", "SSH 凭据类型不正确");
        }
        try {
            CredentialCipher.EncryptedSecret secret = objectMapper.readValue(encrypted.encryptedPayload(), CredentialCipher.EncryptedSecret.class);
            byte[] plainBytes = credentialCipher.decrypt(secret);
            Map<?, ?> payload = objectMapper.readValue(plainBytes, Map.class);
            String username = stringValue(payload.get("username"));
            if (encrypted.kind() == CredentialKind.SSH_PASSWORD) {
                return new SshRuntimeCredential(
                        view.id(),
                        CredentialKind.SSH_PASSWORD,
                        username,
                        stringValue(payload.get("password")),
                        null,
                        null
                );
            }
            return new SshRuntimeCredential(
                    view.id(),
                    CredentialKind.SSH_KEY,
                    username,
                    null,
                    stringValue(payload.get("privateKey")),
                    stringValue(payload.get("passphrase"))
            );
        } catch (IOException | IllegalStateException ex) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "CREDENTIAL_DECRYPT_FAILED", "SSH 凭据无法解密");
        }
    }

    public GitRuntimeCredential gitRuntimeCredential(UUID credentialId, UUID projectId) {
        CredentialView view = requireActive(credentialId, projectId);
        CredentialRepository.EncryptedCredentialRecord encrypted = credentialRepository.findActiveEncryptedById(credentialId)
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "CREDENTIAL_NOT_FOUND", "凭据不存在"));
        if (encrypted.kind() != CredentialKind.GIT_PASSWORD && encrypted.kind() != CredentialKind.GIT_TOKEN) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "CREDENTIAL_KIND_INVALID", "Git 凭据类型不正确");
        }
        try {
            CredentialCipher.EncryptedSecret secret = objectMapper.readValue(encrypted.encryptedPayload(), CredentialCipher.EncryptedSecret.class);
            byte[] plainBytes = credentialCipher.decrypt(secret);
            Map<?, ?> payload = objectMapper.readValue(plainBytes, Map.class);
            return new GitRuntimeCredential(
                    view.id(),
                    encrypted.kind(),
                    stringValue(payload.get("username")),
                    stringValue(payload.get("secret"))
            );
        } catch (IOException | IllegalStateException ex) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "CREDENTIAL_DECRYPT_FAILED", "Git 凭据无法解密");
        }
    }

    public CreateCredentialCommand sshPassword(UUID projectId, UUID ownerUserId, String name, String host, String username, String password) {
        if (password == null || password.isBlank()) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "CREDENTIAL_SECRET_REQUIRED", "SSH 密码不能为空");
        }
        return new CreateCredentialCommand(
                projectId,
                ownerUserId,
                CredentialKind.SSH_PASSWORD,
                displayName(name, "SSH password"),
                username + "@" + host,
                Map.of("type", "password", "username", username, "password", password)
        );
    }

    public CreateCredentialCommand sshKey(
            UUID projectId,
            UUID ownerUserId,
            String name,
            String host,
            String username,
            String privateKey,
            String passphrase
    ) {
        if (privateKey == null || privateKey.isBlank()) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "CREDENTIAL_SECRET_REQUIRED", "SSH 私钥不能为空");
        }
        return new CreateCredentialCommand(
                projectId,
                ownerUserId,
                CredentialKind.SSH_KEY,
                displayName(name, "SSH key"),
                username + "@" + host,
                Map.of(
                        "type", "key",
                        "username", username,
                        "privateKey", privateKey,
                        "passphrase", passphrase == null ? "" : passphrase
                )
        );
    }

    public CreateCredentialCommand gitSecret(
            UUID projectId,
            UUID ownerUserId,
            CredentialKind kind,
            String name,
            String gitUrl,
            String username,
            String secret
    ) {
        if (kind != CredentialKind.GIT_PASSWORD && kind != CredentialKind.GIT_TOKEN) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "CREDENTIAL_KIND_INVALID", "Git 凭据类型不正确");
        }
        if (secret == null || secret.isBlank()) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "CREDENTIAL_SECRET_REQUIRED", "Git 凭据不能为空");
        }
        String masked = kind == CredentialKind.GIT_TOKEN ? maskTail(secret) : displayName(username, "git-user");
        return new CreateCredentialCommand(
                projectId,
                ownerUserId,
                kind,
                displayName(name, "Git credential"),
                masked,
                Map.of(
                        "type", kind.name(),
                        "gitUrl", gitUrl,
                        "username", username == null ? "" : username,
                        "secret", secret
                )
        );
    }

    public String encryptedPayloadForTests(CreateCredentialCommand command) {
        CredentialCipher.EncryptedSecret encrypted = credentialCipher.encrypt(toBytes(command.payload()));
        try {
            return objectMapper.writeValueAsString(encrypted);
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException(ex);
        }
    }

    private void validate(CreateCredentialCommand command) {
        if (command.projectId() == null || command.ownerUserId() == null) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", "凭据项目和所有者不能为空");
        }
        if (command.kind() == null || command.name() == null || command.name().isBlank()) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", "凭据类型和名称不能为空");
        }
    }

    private byte[] toBytes(Map<String, ?> payload) {
        try {
            return objectMapper.writeValueAsBytes(payload);
        } catch (JsonProcessingException ex) {
            return "{}".getBytes(StandardCharsets.UTF_8);
        }
    }

    private String displayName(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value.trim();
    }

    private String maskTail(String secret) {
        String trimmed = secret.trim();
        if (trimmed.length() <= 4) {
            return "****";
        }
        return "****" + trimmed.substring(trimmed.length() - 4);
    }

    private String stringValue(Object value) {
        return value == null ? "" : value.toString();
    }

    public record SshRuntimeCredential(
            UUID credentialId,
            CredentialKind kind,
            String username,
            String password,
            String privateKey,
            String passphrase
    ) {
    }

    public record GitRuntimeCredential(
            UUID credentialId,
            CredentialKind kind,
            String username,
            String secret
    ) {
    }
}
