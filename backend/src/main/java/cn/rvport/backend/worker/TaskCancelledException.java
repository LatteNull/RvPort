package cn.rvport.backend.worker;

public class TaskCancelledException extends RuntimeException {

    public TaskCancelledException(String message) {
        super(message);
    }
}
