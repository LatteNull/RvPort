package cn.rvport.backend.health;

import cn.rvport.backend.common.web.ApiResponse;
import cn.rvport.backend.common.web.TraceIdFilter;
import jakarta.servlet.http.HttpServletRequest;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class HealthController {

    @GetMapping({"/health", "/api/health"})
    public ApiResponse<Map<String, String>> health(HttpServletRequest request) {
        return ApiResponse.ok(Map.of("status", "UP"), TraceIdFilter.currentTraceId(request));
    }
}
