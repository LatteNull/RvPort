package cn.rvport.backend.task;

import java.io.IOException;
import java.time.Duration;
import java.util.Collection;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

@Component
public class TaskLogNotificationBroker {

    private static final Logger log = LoggerFactory.getLogger(TaskLogNotificationBroker.class);
    private static final long TIMEOUT_MILLIS = Duration.ofHours(2).toMillis();

    private final TaskRepository taskRepository;
    private final TaskLogEventRepository taskLogEventRepository;
    private final ConcurrentHashMap<UUID, Set<Subscription>> subscriptions = new ConcurrentHashMap<>();

    public TaskLogNotificationBroker(TaskRepository taskRepository, TaskLogEventRepository taskLogEventRepository) {
        this.taskRepository = taskRepository;
        this.taskLogEventRepository = taskLogEventRepository;
    }

    public SseEmitter subscribe(TaskView authorizedTask, long afterEventId) {
        return subscribe(authorizedTask, afterEventId, new SseEmitter(TIMEOUT_MILLIS));
    }

    SseEmitter subscribe(TaskView authorizedTask, long afterEventId, SseEmitter emitter) {
        UUID taskId = authorizedTask.id();
        Subscription subscription = new Subscription(emitter, afterEventId);
        subscriptions.computeIfAbsent(taskId, ignored -> ConcurrentHashMap.newKeySet()).add(subscription);
        emitter.onCompletion(() -> remove(taskId, subscription));
        emitter.onTimeout(() -> remove(taskId, subscription));
        emitter.onError(ignored -> remove(taskId, subscription));
        refresh(Set.of(taskId));
        return emitter;
    }

    @Scheduled(fixedDelayString = "${rvport.sse.task-log-notification-interval-ms:5000}")
    public void poll() {
        refresh(Set.copyOf(subscriptions.keySet()));
    }

    @Scheduled(fixedDelayString = "${rvport.sse.heartbeat-interval-ms:15000}")
    public void heartbeat() {
        subscriptions.forEach((taskId, taskSubscriptions) -> taskSubscriptions.forEach(subscription -> {
            try {
                subscription.emitter().send(SseEmitter.event()
                        .name("heartbeat")
                        .comment("keepalive")
                        .data("{}", MediaType.APPLICATION_JSON));
            } catch (IOException | IllegalStateException ex) {
                remove(taskId, subscription);
            }
        }));
    }

    void refresh(Collection<UUID> taskIds) {
        if (taskIds == null || taskIds.isEmpty()) {
            return;
        }
        Map<UUID, TaskView> tasks = taskRepository.findByIds(taskIds);
        Map<UUID, Long> latestEventIds = taskLogEventRepository.latestEventIds(taskIds);
        for (UUID taskId : taskIds) {
            TaskView task = tasks.get(taskId);
            if (task == null) {
                completeMissing(taskId);
                continue;
            }
            long latestEventId = latestEventIds.getOrDefault(taskId, 0L);
            notifySubscriptions(task, latestEventId);
        }
    }

    int subscribedTaskCount() {
        return subscriptions.size();
    }

    private void notifySubscriptions(TaskView task, long latestEventId) {
        Set<Subscription> taskSubscriptions = subscriptions.get(task.id());
        if (taskSubscriptions == null) {
            return;
        }
        for (Subscription subscription : taskSubscriptions) {
            try {
                if (latestEventId > subscription.lastNotifiedEventId().get()) {
                    subscription.emitter().send(updatedEvent(task, latestEventId));
                    subscription.lastNotifiedEventId().set(latestEventId);
                }
                if (taskRepository.isTerminal(task.status())) {
                    subscription.emitter().send(completedEvent(task, latestEventId));
                    subscription.emitter().complete();
                    remove(task.id(), subscription);
                }
            } catch (IOException | IllegalStateException ex) {
                remove(task.id(), subscription);
            }
        }
    }

    private SseEmitter.SseEventBuilder updatedEvent(TaskView task, long latestEventId) {
        return SseEmitter.event()
                .name("task.log.updated")
                .data(Map.of(
                        "taskId", task.id(),
                        "latestEventId", latestEventId,
                        "status", task.status().name()
                ), MediaType.APPLICATION_JSON);
    }

    private SseEmitter.SseEventBuilder completedEvent(TaskView task, long latestEventId) {
        return SseEmitter.event()
                .name("task.log.completed")
                .data(Map.of(
                        "taskId", task.id(),
                        "latestEventId", latestEventId,
                        "status", task.status().name(),
                        "message", task.message() == null ? "" : task.message()
                ), MediaType.APPLICATION_JSON);
    }

    private void completeMissing(UUID taskId) {
        Set<Subscription> removed = subscriptions.remove(taskId);
        if (removed != null) {
            removed.forEach(subscription -> subscription.emitter().complete());
        }
    }

    private void remove(UUID taskId, Subscription subscription) {
        Set<Subscription> taskSubscriptions = subscriptions.get(taskId);
        if (taskSubscriptions == null) {
            return;
        }
        taskSubscriptions.remove(subscription);
        if (taskSubscriptions.isEmpty()) {
            subscriptions.remove(taskId, taskSubscriptions);
        }
        log.debug("Removed task log notification SSE emitter taskId={}", taskId);
    }

    private record Subscription(SseEmitter emitter, AtomicLong lastNotifiedEventId) {
        private Subscription(SseEmitter emitter, long lastNotifiedEventId) {
            this(emitter, new AtomicLong(lastNotifiedEventId));
        }
    }
}
