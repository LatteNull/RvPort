package cn.rvport.backend.environment.runtime;

public class SshRuntimeException extends RuntimeException {

    private final String errorCode;

    public SshRuntimeException(String message) {
        this(null, message, null);
    }

    public SshRuntimeException(String message, Throwable cause) {
        this(null, message, cause);
    }

    public SshRuntimeException(String errorCode, String message, Throwable cause) {
        super(message, cause);
        this.errorCode = errorCode;
    }

    public String errorCode() {
        return errorCode;
    }
}
