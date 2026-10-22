package cn.rvport.backend.analysis;

import cn.rvport.backend.task.TaskErrorCode;
import cn.rvport.backend.task.TaskExecutionException;

public class SpecializedAnalysisRuntimeException extends TaskExecutionException {
    public SpecializedAnalysisRuntimeException(String message) {
        this(TaskErrorCode.ANALYSIS_NON_RETRYABLE, message, null);
    }

    public SpecializedAnalysisRuntimeException(String message, Throwable cause) {
        this(TaskErrorCode.ANALYSIS_NON_RETRYABLE, message, cause);
    }

    public SpecializedAnalysisRuntimeException(String errorCode, String message) {
        this(errorCode, message, null);
    }

    public SpecializedAnalysisRuntimeException(String errorCode, String message, Throwable cause) {
        super(errorCode, message, cause);
    }
}
