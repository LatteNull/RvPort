package cn.rvport.backend.task;

public class TaskExecutionException extends RuntimeException {

    private final String errorCode;
    private final String safeMessage;

    public TaskExecutionException(String errorCode, String safeMessage, Throwable cause) {
        super(safeMessage, cause);
        this.errorCode = errorCode;
        this.safeMessage = safeMessage;
    }

    public String errorCode() {
        return errorCode;
    }

    public String safeMessage() {
        return safeMessage;
    }
}
