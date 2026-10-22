package cn.rvport.backend.cache;

import java.time.Duration;
import java.util.Optional;
import java.util.concurrent.TimeUnit;

import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import tools.jackson.databind.ObjectMapper;
import tools.jackson.databind.json.JsonMapper;

@Component
public class RedisCacheClient {

    private final StringRedisTemplate redisTemplate;
    private final RedisKeyFactory keyFactory;
    private final ObjectMapper objectMapper;

    @Autowired
    public RedisCacheClient(StringRedisTemplate redisTemplate, RedisKeyFactory keyFactory) {
        this(redisTemplate, keyFactory, JsonMapper.builder().findAndAddModules().build());
    }

    RedisCacheClient(StringRedisTemplate redisTemplate, RedisKeyFactory keyFactory, ObjectMapper objectMapper) {
        this.redisTemplate = redisTemplate;
        this.keyFactory = keyFactory;
        this.objectMapper = objectMapper;
    }

    public <T> void set(RedisKey key, T value, Duration ttl) {
        requireTtl(ttl);
        try {
            redisTemplate.opsForValue().set(keyFactory.format(key), objectMapper.writeValueAsString(value), ttl);
        } catch (Exception e) {
            throw new RedisCacheException("Failed to serialize Redis cache value.", e);
        }
    }

    public <T> Optional<T> get(RedisKey key, Class<T> type) {
        String value = redisTemplate.opsForValue().get(keyFactory.format(key));
        if (value == null) {
            return Optional.empty();
        }

        try {
            return Optional.of(objectMapper.readValue(value, type));
        } catch (Exception e) {
            throw new RedisCacheException("Failed to deserialize Redis cache value.", e);
        }
    }

    public void delete(RedisKey key) {
        redisTemplate.delete(keyFactory.format(key));
    }

    public Long increment(RedisKey key, Duration ttl) {
        requireTtl(ttl);
        Long value = redisTemplate.opsForValue().increment(keyFactory.format(key));
        redisTemplate.expire(keyFactory.format(key), ttl.toMillis(), TimeUnit.MILLISECONDS);
        return value;
    }

    public void expire(RedisKey key, Duration ttl) {
        requireTtl(ttl);
        redisTemplate.expire(keyFactory.format(key), ttl.toMillis(), TimeUnit.MILLISECONDS);
    }

    private static void requireTtl(Duration ttl) {
        if (ttl == null || ttl.isZero() || ttl.isNegative()) {
            throw new IllegalArgumentException("Redis cache writes require a positive TTL.");
        }
    }
}
