package cn.rvport.backend.modelprofile;

import java.time.Instant;
import java.util.Map;

public record ModelProfileConnectivityTestResult(
        boolean success,
        String status,
        String message,
        Instant testedAt,
        long durationMs,
        Map<String, Object> details
) {
}
