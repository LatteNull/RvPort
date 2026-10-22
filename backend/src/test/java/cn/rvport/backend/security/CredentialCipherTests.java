package cn.rvport.backend.security;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.config.CredentialCryptoProperties;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import org.junit.jupiter.api.Test;

class CredentialCipherTests {

    @Test
    void encryptsAndDecryptsWithConfiguredKeyId() {
        CredentialCipher cipher = cipher(validKey(), "key-2026");

        CredentialCipher.EncryptedSecret encrypted = cipher.encrypt("sensitive".getBytes(StandardCharsets.UTF_8));

        assertThat(encrypted.algorithm()).isEqualTo(CredentialCipher.ALGORITHM);
        assertThat(encrypted.keyId()).isEqualTo("key-2026");
        assertThat(encrypted.iv()).isNotBlank();
        assertThat(encrypted.cipherText()).doesNotContain("sensitive");
        assertThat(cipher.decrypt(encrypted)).isEqualTo("sensitive".getBytes(StandardCharsets.UTF_8));
    }

    @Test
    void defaultsBlankOrMissingKeyId() {
        assertThat(cipher(validKey(), null).encrypt(new byte[0]).keyId()).isEqualTo("local-v1");
        assertThat(cipher(validKey(), " ").encrypt(new byte[0]).keyId()).isEqualTo("local-v1");
    }

    @Test
    void rejectsMissingBlankMalformedAndWrongLengthKeys() {
        assertKeyFailure(null, "not configured");
        assertKeyFailure(" ", "not configured");
        assertKeyFailure("not-base64", "Illegal base64");
        assertKeyFailure(Base64.getEncoder().encodeToString(new byte[16]), "must be 32 bytes");
    }

    @Test
    void rejectsTamperedCiphertextAndInvalidIv() {
        CredentialCipher cipher = cipher(validKey(), "key");
        CredentialCipher.EncryptedSecret encrypted = cipher.encrypt("secret".getBytes(StandardCharsets.UTF_8));
        byte[] modified = Base64.getDecoder().decode(encrypted.cipherText());
        modified[0] ^= 1;
        CredentialCipher.EncryptedSecret tampered = new CredentialCipher.EncryptedSecret(
                encrypted.algorithm(), encrypted.keyId(), encrypted.iv(), Base64.getEncoder().encodeToString(modified));

        assertThatThrownBy(() -> cipher.decrypt(tampered)).isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("decrypt");
        CredentialCipher.EncryptedSecret badIv = new CredentialCipher.EncryptedSecret(
                encrypted.algorithm(), encrypted.keyId(), "***", encrypted.cipherText());
        assertThatThrownBy(() -> cipher.decrypt(badIv)).isInstanceOf(IllegalArgumentException.class);
    }

    private void assertKeyFailure(String key, String message) {
        assertThatThrownBy(() -> cipher(key, null).encrypt(new byte[0]))
                .isInstanceOfAny(IllegalStateException.class, IllegalArgumentException.class)
                .hasMessageContaining(message);
    }

    private CredentialCipher cipher(String key, String keyId) {
        return new CredentialCipher(new CredentialCryptoProperties(key, keyId));
    }

    private String validKey() {
        return Base64.getEncoder().encodeToString(new byte[32]);
    }
}
