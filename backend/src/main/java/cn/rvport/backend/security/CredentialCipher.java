package cn.rvport.backend.security;

import cn.rvport.backend.config.CredentialCryptoProperties;
import java.security.GeneralSecurityException;
import java.security.SecureRandom;
import java.util.Base64;
import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import org.springframework.stereotype.Component;

@Component
public class CredentialCipher {

    public static final String ALGORITHM = "AES-256-GCM";
    private static final String JCA_ALGORITHM = "AES/GCM/NoPadding";
    private static final int KEY_BYTES = 32;
    private static final int IV_BYTES = 12;
    private static final int TAG_BITS = 128;

    private final CredentialCryptoProperties properties;
    private final SecureRandom secureRandom = new SecureRandom();

    public CredentialCipher(CredentialCryptoProperties properties) {
        this.properties = properties;
    }

    public EncryptedSecret encrypt(byte[] plainText) {
        try {
            byte[] iv = new byte[IV_BYTES];
            secureRandom.nextBytes(iv);
            Cipher cipher = Cipher.getInstance(JCA_ALGORITHM);
            cipher.init(Cipher.ENCRYPT_MODE, key(), new GCMParameterSpec(TAG_BITS, iv));
            byte[] cipherText = cipher.doFinal(plainText);
            return new EncryptedSecret(ALGORITHM, keyId(), Base64.getEncoder().encodeToString(iv),
                    Base64.getEncoder().encodeToString(cipherText));
        } catch (GeneralSecurityException ex) {
            throw new IllegalStateException("Failed to encrypt credential payload", ex);
        }
    }

    public byte[] decrypt(EncryptedSecret secret) {
        try {
            Cipher cipher = Cipher.getInstance(JCA_ALGORITHM);
            byte[] iv = Base64.getDecoder().decode(secret.iv());
            byte[] cipherText = Base64.getDecoder().decode(secret.cipherText());
            cipher.init(Cipher.DECRYPT_MODE, key(), new GCMParameterSpec(TAG_BITS, iv));
            return cipher.doFinal(cipherText);
        } catch (GeneralSecurityException ex) {
            throw new IllegalStateException("Failed to decrypt credential payload", ex);
        }
    }

    private SecretKeySpec key() {
        String configuredKey = properties.masterKey();
        if (configuredKey == null || configuredKey.isBlank()) {
            throw new IllegalStateException("Credential master key is not configured");
        }
        byte[] keyBytes = Base64.getDecoder().decode(configuredKey);
        if (keyBytes.length != KEY_BYTES) {
            throw new IllegalStateException("Credential master key must be 32 bytes after base64 decoding");
        }
        return new SecretKeySpec(keyBytes, "AES");
    }

    private String keyId() {
        return properties.keyId() == null || properties.keyId().isBlank() ? "local-v1" : properties.keyId();
    }

    public record EncryptedSecret(
            String algorithm,
            String keyId,
            String iv,
            String cipherText
    ) {
    }
}
