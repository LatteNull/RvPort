package cn.rvport.backend.audit;

import static cn.rvport.backend.jooq.tables.AuditLogs.AUDIT_LOGS;

import cn.rvport.backend.common.web.TraceIdFilter;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import java.util.Map;
import java.util.UUID;
import org.jooq.DSLContext;
import org.jooq.JSONB;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

@Service
public class AuditLogService {

    private static final Logger log = LoggerFactory.getLogger(AuditLogService.class);

    private final DSLContext dsl;
    private final ObjectMapper objectMapper;

    public AuditLogService(DSLContext dsl, ObjectMapper objectMapper) {
        this.dsl = dsl;
        this.objectMapper = objectMapper;
    }

    public void record(
            UUID userId,
            String action,
            String resourceType,
            UUID resourceId,
            Map<String, ?> details,
            HttpServletRequest request
    ) {
        record(null, userId, action, resourceType, resourceId, details, request);
    }

    public void record(
            UUID projectId,
            UUID userId,
            String action,
            String resourceType,
            UUID resourceId,
            Map<String, ?> details,
            HttpServletRequest request
    ) {
        try {
            dsl.insertInto(AUDIT_LOGS)
                    .set(AUDIT_LOGS.PROJECT_ID, projectId)
                    .set(AUDIT_LOGS.USER_ID, userId)
                    .set(AUDIT_LOGS.ACTION, action)
                    .set(AUDIT_LOGS.RESOURCE_TYPE, resourceType)
                    .set(AUDIT_LOGS.RESOURCE_ID, resourceId)
                    .set(AUDIT_LOGS.USER_AGENT, request == null ? null : request.getHeader("User-Agent"))
                    .set(AUDIT_LOGS.REQUEST_ID, request == null ? null : TraceIdFilter.currentTraceId(request))
                    .set(AUDIT_LOGS.DETAILS, JSONB.valueOf(toJson(details == null ? Map.of() : details)))
                    .execute();
        } catch (RuntimeException ex) {
            log.warn("Failed to write audit log action={}", action, ex);
        }
    }

    private String toJson(Map<String, ?> details) {
        try {
            return objectMapper.writeValueAsString(details);
        } catch (JsonProcessingException ex) {
            return "{}";
        }
    }
}
