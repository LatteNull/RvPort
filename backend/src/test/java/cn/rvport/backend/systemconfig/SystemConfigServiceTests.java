package cn.rvport.backend.systemconfig;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.config.CredentialCryptoProperties;
import cn.rvport.backend.security.CredentialCipher;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
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
class SystemConfigServiceTests {

    @Mock
    private SystemConfigRepository repository;

    @Test
    void savesSecretEncryptedAndReadsPlainValue() {
        SystemConfigService service = service();
        UUID actorId = UUID.randomUUID();
        ArgumentCaptor<String> valueCaptor = ArgumentCaptor.forClass(String.class);

        service.saveSecret("mail", "password", "Secret123", actorId);

        verify(repository).upsert(eq("mail"), eq("password"), valueCaptor.capture(), eq(SystemConfigValueType.SECRET), eq(true), eq(actorId));
        assertThat(valueCaptor.getValue()).doesNotContain("Secret123");

        when(repository.find("mail", "password"))
                .thenReturn(Optional.of(new SystemConfigEntry("mail", "password", valueCaptor.getValue(), SystemConfigValueType.SECRET, true)));
        assertThat(service.plainValue("mail", "password")).contains("Secret123");
    }

    @Test
    void deletesPlainValueWhenNullAndReturnsNamespaceEntries() {
        SystemConfigService service = service();
        service.savePlain("mail", "host", null, SystemConfigValueType.STRING, UUID.randomUUID());

        verify(repository).delete("mail", "host");
        when(repository.findNamespace("mail")).thenReturn(Map.of("host", new SystemConfigEntry("mail", "host", "smtp.example.com", SystemConfigValueType.STRING, false)));

        assertThat(service.findNamespace("mail")).containsKey("host");
    }

    @Test
    void storesAndReadsUnencryptedPlainValues() {
        SystemConfigService service = service();
        UUID actor = UUID.randomUUID();

        service.savePlain("mail", "port", "587", SystemConfigValueType.NUMBER, actor);
        verify(repository).upsert("mail", "port", "587", SystemConfigValueType.NUMBER, false, actor);
        verify(repository, never()).delete("mail", "port");

        when(repository.find("mail", "host")).thenReturn(Optional.of(
                new SystemConfigEntry("mail", "host", "smtp.example.com", SystemConfigValueType.STRING, false)));
        assertThat(service.plainValue("mail", "host")).contains("smtp.example.com");
        when(repository.find("mail", "missing")).thenReturn(Optional.empty());
        assertThat(service.plainValue("mail", "missing")).isEmpty();
    }

    @Test
    void ignoresNullSecretAndDeletesBlankSecret() {
        SystemConfigService service = service();
        UUID actor = UUID.randomUUID();

        service.saveSecret("mail", "password", null, actor);
        verifyNoInteractions(repository);
        service.saveSecret("mail", "password", " ", actor);
        verify(repository).delete("mail", "password");
    }

    @Test
    void reportsMalformedEncryptedConfigurationWithoutLeakingPayload() {
        SystemConfigService service = service();
        when(repository.find("mail", "password")).thenReturn(Optional.of(
                new SystemConfigEntry("mail", "password", "not-json", SystemConfigValueType.SECRET, true)));

        assertThatThrownBy(() -> service.plainValue("mail", "password"))
                .isInstanceOf(cn.rvport.backend.common.error.ApiException.class)
                .extracting("code")
                .isEqualTo("CONFIG_SECRET_DECRYPT_FAILED");
    }

    private SystemConfigService service() {
        String key = Base64.getEncoder().encodeToString("0123456789abcdef0123456789abcdef".getBytes(StandardCharsets.UTF_8));
        return new SystemConfigService(
                repository,
                new CredentialCipher(new CredentialCryptoProperties(key, "local-v1")),
                new ObjectMapper()
        );
    }
}
