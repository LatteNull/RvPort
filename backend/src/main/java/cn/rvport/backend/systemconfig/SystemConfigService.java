package cn.rvport.backend.systemconfig;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.security.CredentialCipher;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

@Service
public class SystemConfigService {

    private final SystemConfigRepository repository;
    private final CredentialCipher credentialCipher;
    private final ObjectMapper objectMapper;

    public SystemConfigService(
            SystemConfigRepository repository,
            CredentialCipher credentialCipher,
            ObjectMapper objectMapper
    ) {
        this.repository = repository;
        this.credentialCipher = credentialCipher;
        this.objectMapper = objectMapper;
    }

    public Map<String, SystemConfigEntry> findNamespace(String namespace) {
        return repository.findNamespace(namespace);
    }

    public Optional<String> plainValue(String namespace, String key) {
        return repository.find(namespace, key)
                .map(entry -> entry.encrypted() ? decrypt(entry.value()) : entry.value());
    }

    public void savePlain(String namespace, String key, String value, SystemConfigValueType valueType, UUID updatedBy) {
        if (value == null) {
            repository.delete(namespace, key);
            return;
        }
        repository.upsert(namespace, key, value, valueType, false, updatedBy);
    }

    public void saveSecret(String namespace, String key, String value, UUID updatedBy) {
        if (value == null) {
            return;
        }
        if (value.isBlank()) {
            repository.delete(namespace, key);
            return;
        }
        repository.upsert(namespace, key, encrypt(value), SystemConfigValueType.SECRET, true, updatedBy);
    }

    private String encrypt(String value) {
        try {
            CredentialCipher.EncryptedSecret encrypted = credentialCipher.encrypt(value.getBytes(StandardCharsets.UTF_8));
            return objectMapper.writeValueAsString(encrypted);
        } catch (JsonProcessingException | IllegalStateException ex) {
            throw new ApiException(HttpStatus.INTERNAL_SERVER_ERROR, "CONFIG_SECRET_ENCRYPT_FAILED", "配置密钥加密失败");
        }
    }

    private String decrypt(String stored) {
        try {
            CredentialCipher.EncryptedSecret encrypted = objectMapper.readValue(stored, CredentialCipher.EncryptedSecret.class);
            return new String(credentialCipher.decrypt(encrypted), StandardCharsets.UTF_8);
        } catch (Exception ex) {
            throw new ApiException(HttpStatus.INTERNAL_SERVER_ERROR, "CONFIG_SECRET_DECRYPT_FAILED", "配置密钥解密失败");
        }
    }
}
