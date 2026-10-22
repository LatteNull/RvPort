package cn.rvport.backend.task;

import java.util.UUID;
import org.springframework.stereotype.Component;

@Component
public class TaskSseBroadcastInstance {

    private final String publisherId = UUID.randomUUID().toString();

    public String publisherId() {
        return publisherId;
    }
}
