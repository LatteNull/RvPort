package cn.rvport.backend.cache;

public class RedisCacheException extends RuntimeException {

    public RedisCacheException(String message, Throwable cause) {
        super(message, cause);
    }
}
