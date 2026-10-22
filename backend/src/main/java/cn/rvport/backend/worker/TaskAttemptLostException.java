package cn.rvport.backend.worker;

public class TaskAttemptLostException extends RuntimeException {
    public TaskAttemptLostException() {
        super("Task execution attempt no longer owns the task");
    }
}
