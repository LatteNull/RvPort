package cn.rvport.backend.task;

import java.io.IOException;
import java.time.Duration;
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
public class TaskSseBroker {

    private static final Logger log = LoggerFactory.getLogger(TaskSseBroker.class);
    private static final long TIMEOUT_MILLIS = Duration.ofHours(2).toMillis();

    private final ConcurrentHashMap<UUID, Set<SseEmitter>> emitters = new ConcurrentHashMap<>();

    public SseEmitter subscribe(UUID projectId) {
        SseEmitter emitter = new SseEmitter(TIMEOUT_MILLIS);
        emitters.computeIfAbsent(projectId, ignored -> ConcurrentHashMap.newKeySet()).add(emitter);
        emitter.onCompletion(() -> remove(projectId, emitter));
        emitter.onTimeout(() -> remove(projectId, emitter));
        emitter.onError(ignored -> remove(projectId, emitter));
        return emitter;
    }

    public void publish(TaskEventView event) {
        Set<SseEmitter> projectEmitters = emitters.get(event.projectId());
        if (projectEmitters == null || projectEmitters.isEmpty()) {
            return;
        }
        for (SseEmitter emitter : projectEmitters) {
            try {
                emitter.send(toSseEvent(event));
            } catch (IOException | IllegalStateException ex) {
                remove(event.projectId(), emitter);
            }
        }
    }

    @Scheduled(fixedDelayString = "${rvport.sse.heartbeat-interval-ms:15000}")
    public void heartbeat() {
        emitters.forEach((projectId, projectEmitters) -> {
            for (SseEmitter emitter : projectEmitters) {
                try {
                    emitter.send(SseEmitter.event()
                            .name("heartbeat")
                            .comment("keepalive")
                            .data("{}", MediaType.APPLICATION_JSON));
                } catch (IOException | IllegalStateException ex) {
                    remove(projectId, emitter);
                }
            }
        });
    }

    public SseEmitter.SseEventBuilder toSseEvent(TaskEventView event) {
        return SseEmitter.event()
                .id(Long.toString(event.id()))
                .name(event.eventType())
                .data(event, MediaType.APPLICATION_JSON);
    }

    private void remove(UUID projectId, SseEmitter emitter) {
        Set<SseEmitter> projectEmitters = emitters.get(projectId);
        if (projectEmitters == null) {
            return;
        }
        projectEmitters.remove(emitter);
        if (projectEmitters.isEmpty()) {
            emitters.remove(projectId, projectEmitters);
        }
        log.debug("Removed task SSE emitter projectId={}", projectId);
    }
}
