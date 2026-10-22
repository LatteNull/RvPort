package cn.rvport.backend.worker;

public class TaskRetryableException extends RuntimeException {

    public TaskRetryableException(String message, Throwable cause) {
        super(message, cause);
    }
}
