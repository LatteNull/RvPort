package cn.rvport.backend.cache;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.mockito.Mockito.never;

import java.time.Duration;

import org.junit.jupiter.api.Test;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;
import tools.jackson.databind.json.JsonMapper;
import tools.jackson.databind.ObjectMapper;

class RedisCacheClientTests {

    @Test
    void setRequiresPositiveTtl() {
        RedisCacheClient client = new RedisCacheClient(
                mock(StringRedisTemplate.class),
                new RedisKeyFactory("rvport:cache"),
                JsonMapper.builder().findAndAddModules().build());

        assertThatThrownBy(() -> client.set(RedisKey.of("auth", "nonce", "n1"), "value", Duration.ZERO))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("positive TTL");
    }

    @Test
    void setSerializesJsonValueWithReadableKey() {
        StringRedisTemplate redisTemplate = mock(StringRedisTemplate.class);
        @SuppressWarnings("unchecked")
        ValueOperations<String, String> valueOperations = mock(ValueOperations.class);
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);

        RedisCacheClient client = new RedisCacheClient(
                redisTemplate,
                new RedisKeyFactory("rvport:cache"),
                JsonMapper.builder().findAndAddModules().build());

        client.set(RedisKey.of("auth", "nonce", "n1"), new SampleValue("ok"), Duration.ofMinutes(5));

        verify(valueOperations).set(
                "rvport:cache:auth:nonce:n1",
                "{\"value\":\"ok\"}",
                Duration.ofMinutes(5));
    }

    @Test
    void publicConstructorBuildsDefaultMapperWithoutConnecting() {
        new RedisCacheClient(mock(StringRedisTemplate.class), new RedisKeyFactory("rvport:cache"));
    }

    @Test
    void getReturnsEmptyOrDeserializedValue() throws Exception {
        StringRedisTemplate redisTemplate = mock(StringRedisTemplate.class);
        @SuppressWarnings("unchecked")
        ValueOperations<String, String> operations = mock(ValueOperations.class);
        ObjectMapper mapper = mock(ObjectMapper.class);
        when(redisTemplate.opsForValue()).thenReturn(operations);
        when(operations.get("prefix:auth:user:1")).thenReturn(null, "json");
        when(mapper.readValue("json", SampleValue.class)).thenReturn(new SampleValue("ok"));
        RedisCacheClient client = new RedisCacheClient(redisTemplate, new RedisKeyFactory("prefix"), mapper);
        RedisKey key = RedisKey.of("auth", "user", "1");

        assertThat(client.get(key, SampleValue.class)).isEmpty();
        assertThat(client.get(key, SampleValue.class)).contains(new SampleValue("ok"));
    }

    @Test
    void serializationAndDeserializationFailuresAreWrapped() throws Exception {
        StringRedisTemplate redisTemplate = mock(StringRedisTemplate.class);
        @SuppressWarnings("unchecked")
        ValueOperations<String, String> operations = mock(ValueOperations.class);
        ObjectMapper mapper = mock(ObjectMapper.class);
        when(redisTemplate.opsForValue()).thenReturn(operations);
        when(mapper.writeValueAsString(org.mockito.ArgumentMatchers.any())).thenThrow(new IllegalStateException("bad"));
        RedisCacheClient client = new RedisCacheClient(redisTemplate, new RedisKeyFactory("prefix"), mapper);
        RedisKey key = RedisKey.of("auth", "user", "1");

        assertThatThrownBy(() -> client.set(key, "value", Duration.ofSeconds(1)))
                .isInstanceOf(RedisCacheException.class).hasMessageContaining("serialize");

        when(operations.get("prefix:auth:user:1")).thenReturn("bad-json");
        when(mapper.readValue("bad-json", SampleValue.class)).thenThrow(new IllegalStateException("bad"));
        assertThatThrownBy(() -> client.get(key, SampleValue.class))
                .isInstanceOf(RedisCacheException.class).hasMessageContaining("deserialize");
    }

    @Test
    void deleteIncrementAndExpireUseFormattedKeyAndMillisecondTtl() {
        StringRedisTemplate redisTemplate = mock(StringRedisTemplate.class);
        @SuppressWarnings("unchecked")
        ValueOperations<String, String> operations = mock(ValueOperations.class);
        when(redisTemplate.opsForValue()).thenReturn(operations);
        when(operations.increment("prefix:task:attempt:id")).thenReturn(3L);
        RedisCacheClient client = new RedisCacheClient(redisTemplate, new RedisKeyFactory("prefix"),
                JsonMapper.builder().build());
        RedisKey key = RedisKey.of("task", "attempt", "id");

        client.delete(key);
        assertThat(client.increment(key, Duration.ofMillis(250))).isEqualTo(3L);
        client.expire(key, Duration.ofSeconds(2));

        verify(redisTemplate).delete("prefix:task:attempt:id");
        verify(redisTemplate).expire("prefix:task:attempt:id", 250L, java.util.concurrent.TimeUnit.MILLISECONDS);
        verify(redisTemplate).expire("prefix:task:attempt:id", 2000L, java.util.concurrent.TimeUnit.MILLISECONDS);
    }

    @Test
    void everyWriteOperationRejectsNullZeroAndNegativeTtlBeforeRedisCall() {
        StringRedisTemplate redisTemplate = mock(StringRedisTemplate.class);
        RedisCacheClient client = new RedisCacheClient(redisTemplate, new RedisKeyFactory("prefix"),
                JsonMapper.builder().build());
        RedisKey key = RedisKey.of("task", "attempt", "id");

        assertThatThrownBy(() -> client.set(key, "v", null)).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> client.increment(key, Duration.ofSeconds(-1))).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> client.expire(key, Duration.ZERO)).isInstanceOf(IllegalArgumentException.class);
        verify(redisTemplate, never()).opsForValue();
    }

    @Test
    void redisKeyRejectsBlankSegmentsAndColonsAndCopiesParts() {
        assertThatThrownBy(() -> new RedisKey(null, "purpose", java.util.List.of()))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new RedisKey("domain", " ", java.util.List.of()))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new RedisKey("domain", "purpose", java.util.Arrays.asList((String) null)))
                .isInstanceOf(NullPointerException.class);
        assertThatThrownBy(() -> RedisKey.of("domain", "purpose", "a:b"))
                .isInstanceOf(IllegalArgumentException.class);
        assertThat(new RedisKey("domain", "purpose", null).parts()).isEmpty();
        assertThat(RedisKey.of("domain", "purpose", "a").parts()).containsExactly("a");
    }

    private record SampleValue(String value) {
    }
}
