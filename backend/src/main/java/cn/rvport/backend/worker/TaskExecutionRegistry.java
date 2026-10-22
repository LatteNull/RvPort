package cn.rvport.backend.worker;

import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import org.springframework.stereotype.Component;

@Component
public class TaskExecutionRegistry {

    private final ConcurrentMap<UUID, RunningTaskHandle> running = new ConcurrentHashMap<>();

    public void register(RunningTaskHandle handle) {
        RunningTaskHandle previous = running.putIfAbsent(handle.taskId(), handle);
        if (previous != null) {
            throw new IllegalStateException("Task is already registered: " + handle.taskId());
        }
    }

    public Optional<RunningTaskHandle> find(UUID taskId) {
        return Optional.ofNullable(running.get(taskId));
    }

    public int activeCount() {
        return running.size();
    }

    public Set<UUID> runningTaskIds() {
        return Set.copyOf(running.keySet());
    }

    public boolean cancel(UUID taskId) {
        RunningTaskHandle handle = running.get(taskId);
        if (handle == null) {
            return false;
        }
        handle.requestCancel();
        return true;
    }

    public void remove(UUID taskId) {
        running.remove(taskId);
    }

    public void remove(RunningTaskHandle handle) {
        running.remove(handle.taskId(), handle);
    }
}
