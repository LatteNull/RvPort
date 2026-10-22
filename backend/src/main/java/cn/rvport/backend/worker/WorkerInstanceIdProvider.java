package cn.rvport.backend.worker;

import cn.rvport.backend.config.WorkerProperties;
import java.lang.management.ManagementFactory;
import java.net.InetAddress;
import java.util.UUID;
import org.springframework.stereotype.Component;

@Component
public class WorkerInstanceIdProvider {

    private final String workerInstanceId;

    public WorkerInstanceIdProvider(WorkerProperties properties) {
        String configured = properties.instanceId();
        this.workerInstanceId = configured == null || configured.isBlank() ? generated() : configured.trim();
    }

    public String workerInstanceId() {
        return workerInstanceId;
    }

    private String generated() {
        String host;
        try {
            host = InetAddress.getLocalHost().getHostName();
        } catch (Exception ex) {
            host = "unknown-host";
        }
        String runtimeName = ManagementFactory.getRuntimeMXBean().getName().replaceAll("[^A-Za-z0-9._-]", "-");
        return host + "-" + runtimeName + "-" + UUID.randomUUID();
    }
}
