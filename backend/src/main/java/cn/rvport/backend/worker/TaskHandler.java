package cn.rvport.backend.worker;

public interface TaskHandler {

    String taskType();

    TaskHandlerResult handle(TaskExecutionContext context);
}
