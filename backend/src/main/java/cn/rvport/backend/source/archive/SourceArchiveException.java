package cn.rvport.backend.source.archive;

public class SourceArchiveException extends RuntimeException {

    private final SourceArchiveErrorCode code;

    public SourceArchiveException(SourceArchiveErrorCode code, String message) {
        super(message);
        this.code = code;
    }

    public SourceArchiveException(SourceArchiveErrorCode code, String message, Throwable cause) {
        super(message, cause);
        this.code = code;
    }

    public SourceArchiveErrorCode code() {
        return code;
    }
}
