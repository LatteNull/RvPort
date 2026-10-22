package cn.rvport.backend.cache;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;

class RedisKeyFactoryTests {

    @Test
    void formatsNamespacedRedisKey() {
        RedisKeyFactory keyFactory = new RedisKeyFactory("rvport:cache:");

        assertThat(keyFactory.format(RedisKey.of("rate-limit", "login", "admin")))
                .isEqualTo("rvport:cache:rate-limit:login:admin");
    }

    @Test
    void rejectsPartsContainingSeparator() {
        assertThatThrownBy(() -> RedisKey.of("auth", "nonce", "bad:value"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("must not contain");
    }

    @Test
    void rejectsNullBlankNamespacesAndBlankKeyParts() {
        assertThatThrownBy(() -> new RedisKeyFactory(null))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new RedisKeyFactory("   "))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> RedisKey.of("auth", "nonce", " "))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("non-blank");
    }
}
