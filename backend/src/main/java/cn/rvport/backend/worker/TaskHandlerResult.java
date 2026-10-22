package cn.rvport.backend.worker;

public record TaskHandlerResult(
        String message
) {
    public static TaskHandlerResult success(String message) {
        return new TaskHandlerResult(message == null || message.isBlank() ? "任务执行成功" : message);
    }
}
