package cn.rvport.backend.cache;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;

import java.nio.charset.StandardCharsets;

import org.junit.jupiter.api.Test;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.serializer.RedisSerializer;
import org.springframework.data.redis.serializer.StringRedisSerializer;

class RedisCacheConfigurationTests {

    @Test
    void redisTemplateUsesStringSerializersForKeys() {
        RedisCacheConfiguration configuration = new RedisCacheConfiguration();
        RedisTemplate<String, Object> template = configuration.rvportRedisTemplate(mock(RedisConnectionFactory.class));

        assertThat(template.getKeySerializer()).isInstanceOf(StringRedisSerializer.class);
        assertThat(template.getHashKeySerializer()).isInstanceOf(StringRedisSerializer.class);

        @SuppressWarnings("unchecked")
        RedisSerializer<String> keySerializer = (RedisSerializer<String>) template.getKeySerializer();
        byte[] serialized = keySerializer.serialize("rvport:cache:auth:nonce:n1");

        assertThat(new String(serialized, StandardCharsets.UTF_8))
                .isEqualTo("rvport:cache:auth:nonce:n1");
        assertThat(serialized[0]).isNotEqualTo((byte) 0xac);
        assertThat(serialized[1]).isNotEqualTo((byte) 0xed);
    }
}
