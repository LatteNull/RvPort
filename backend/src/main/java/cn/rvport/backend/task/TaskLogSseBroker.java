package cn.rvport.backend.task;

import java.io.IOException;
import java.time.Duration;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

@Component
public class TaskLogSseBroker {

    private static final Logger log = LoggerFactory.getLogger(TaskLogSseBroker.class);
    private static final long TIMEOUT_MILLIS = Duration.ofHours(2).toMillis();

    private final ConcurrentHashMap<UUID, Set<SseEmitter>> emitters = new ConcurrentHashMap<>();

    public SseEmitter subscribe(UUID taskId) {
        SseEmitter emitter = new SseEmitter(TIMEOUT_MILLIS);
        emitters.computeIfAbsent(taskId, ignored -> ConcurrentHashMap.newKeySet()).add(emitter);
        emitter.onCompletion(() -> remove(taskId, emitter));
        emitter.onTimeout(() -> remove(taskId, emitter));
        emitter.onError(ignored -> remove(taskId, emitter));
        return emitter;
    }

    public void publish(TaskLogEventView event) {
        Set<SseEmitter> taskEmitters = emitters.get(event.taskId());
        if (taskEmitters == null || taskEmitters.isEmpty()) {
            return;
        }
        for (SseEmitter emitter : taskEmitters) {
            try {
                emitter.send(toSseEvent(event));
            } catch (IOException | IllegalStateException ex) {
                remove(event.taskId(), emitter);
            }
        }
    }

    public void publishTerminal(TaskView task) {
        Set<SseEmitter> taskEmitters = emitters.get(task.id());
        if (taskEmitters == null || taskEmitters.isEmpty()) {
            return;
        }
        for (SseEmitter emitter : taskEmitters) {
            try {
                emitter.send(toTerminalEvent(task));
                emitter.complete();
            } catch (IOException | IllegalStateException ex) {
                remove(task.id(), emitter);
            }
        }
    }

    @Scheduled(fixedDelayString = "${rvport.sse.heartbeat-interval-ms:15000}")
    public void heartbeat() {
        emitters.forEach((taskId, taskEmitters) -> {
            for (SseEmitter emitter : taskEmitters) {
                try {
                    emitter.send(SseEmitter.event()
                            .name("heartbeat")
                            .comment("keepalive")
                            .data("{}", MediaType.APPLICATION_JSON));
                } catch (IOException | IllegalStateException ex) {
                    remove(taskId, emitter);
                }
            }
        });
    }

    public SseEmitter.SseEventBuilder toSseEvent(TaskLogEventView event) {
        return SseEmitter.event()
                .id(Long.toString(event.id()))
                .name(event.logType().name().toLowerCase())
                .data(event, MediaType.APPLICATION_JSON);
    }

    public SseEmitter.SseEventBuilder toTerminalEvent(TaskView task) {
        return SseEmitter.event()
                .name("terminal")
                .data(Map.of(
                        "taskId", task.id(),
                        "status", task.status().name(),
                        "message", task.message() == null ? "" : task.message()
                ), MediaType.APPLICATION_JSON);
    }

    private void remove(UUID taskId, SseEmitter emitter) {
        Set<SseEmitter> taskEmitters = emitters.get(taskId);
        if (taskEmitters == null) {
            return;
        }
        taskEmitters.remove(emitter);
        if (taskEmitters.isEmpty()) {
            emitters.remove(taskId, taskEmitters);
        }
        log.debug("Removed task log SSE emitter taskId={}", taskId);
    }
}
