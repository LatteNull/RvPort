package cn.rvport.backend.task;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

public record TaskEventResource(
        String type,
        UUID id,
        String mode,
        String environmentRole
) {
    public static TaskEventResource of(String type, UUID id) {
        return new TaskEventResource(type, id, null, null);
    }

    public static TaskEventResource fromTask(TaskView task) {
        if (task == null) {
            return empty();
        }
        String type = task.resourceType() == null || task.resourceType().isBlank()
                ? task.type()
                : task.resourceType();
        UUID id = task.resourceId() == null ? task.id() : task.resourceId();
        return new TaskEventResource(type, id, task.resourceMode(), task.environmentRole());
    }

    public static TaskEventResource empty() {
        return new TaskEventResource(null, null, null, null);
    }

    public Map<String, Object> toMap() {
        Map<String, Object> values = new LinkedHashMap<>();
        put(values, "type", type);
        put(values, "id", id);
        put(values, "mode", mode);
        put(values, "environmentRole", environmentRole);
        return values;
    }

    private static void put(Map<String, Object> values, String key, Object value) {
        if (value != null && (!(value instanceof String text) || !text.isBlank())) {
            values.put(key, value);
        }
    }
}
