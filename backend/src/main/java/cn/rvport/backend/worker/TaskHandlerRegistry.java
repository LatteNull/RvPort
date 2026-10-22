package cn.rvport.backend.worker;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.function.Function;
import java.util.stream.Collectors;
import org.springframework.stereotype.Component;

@Component
public class TaskHandlerRegistry {

    private final Map<String, TaskHandler> handlers;

    public TaskHandlerRegistry(List<TaskHandler> handlers) {
        this.handlers = handlers.stream()
                .collect(Collectors.toUnmodifiableMap(TaskHandler::taskType, Function.identity()));
    }

    public Optional<TaskHandler> find(String taskType) {
        return Optional.ofNullable(handlers.get(taskType));
    }
}
