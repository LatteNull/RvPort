package cn.rvport.backend.cache;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.serializer.GenericJacksonJsonRedisSerializer;
import org.springframework.data.redis.serializer.StringRedisSerializer;
import tools.jackson.databind.ObjectMapper;
import tools.jackson.databind.json.JsonMapper;

@Configuration
public class RedisCacheConfiguration {

    @Bean
    RedisKeyFactory redisKeyFactory(cn.rvport.backend.config.RedisCacheProperties properties) {
        return new RedisKeyFactory(properties.namespace());
    }

    @Bean
    RedisTemplate<String, Object> rvportRedisTemplate(RedisConnectionFactory connectionFactory) {
        ObjectMapper objectMapper = JsonMapper.builder().findAndAddModules().build();
        StringRedisSerializer stringSerializer = StringRedisSerializer.UTF_8;
        GenericJacksonJsonRedisSerializer jsonSerializer = new GenericJacksonJsonRedisSerializer(objectMapper);

        RedisTemplate<String, Object> template = new RedisTemplate<>();
        template.setConnectionFactory(connectionFactory);
        template.setKeySerializer(stringSerializer);
        template.setHashKeySerializer(stringSerializer);
        template.setValueSerializer(jsonSerializer);
        template.setHashValueSerializer(jsonSerializer);
        template.afterPropertiesSet();
        return template;
    }
}
