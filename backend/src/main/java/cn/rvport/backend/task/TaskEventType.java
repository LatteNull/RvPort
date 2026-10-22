package cn.rvport.backend.task;

public enum TaskEventType {
    CREATED("task.created"),
    QUEUED("task.queued"),
    STARTED("task.started"),
    PROGRESS("task.progress"),
    LOG("task.log"),
    SUCCEEDED("task.succeeded"),
    FAILED("task.failed"),
    CANCELLED("task.cancelled"),
    TIMEOUT("task.timeout"),
    PROJECT_CONTEXT_CHANGED("project.context.changed");

    private final String value;

    TaskEventType(String value) {
        this.value = value;
    }

    public String value() {
        return value;
    }
}
