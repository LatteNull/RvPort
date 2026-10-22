package cn.rvport.backend.audit;

import static cn.rvport.backend.jooq.tables.AuditLogs.AUDIT_LOGS;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.RETURNS_DEEP_STUBS;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.Map;
import java.util.UUID;
import org.jooq.DSLContext;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;

class AuditLogServiceTests {

    @Test
    void recordsRequestMetadataAndDetails() throws Exception {
        DSLContext dsl = mock(DSLContext.class, RETURNS_DEEP_STUBS);
        ObjectMapper mapper = mock(ObjectMapper.class);
        when(mapper.writeValueAsString(any())).thenReturn("{\"key\":\"value\"}");
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.addHeader("User-Agent", "unit-test");
        request.setAttribute("traceId", "trace-1");

        new AuditLogService(dsl, mapper).record(UUID.randomUUID(), UUID.randomUUID(), "UPDATE",
                "PROJECT", UUID.randomUUID(), Map.of("key", "value"), request);

        verify(dsl).insertInto(AUDIT_LOGS);
        verify(mapper).writeValueAsString(Map.of("key", "value"));
    }

    @Test
    void supportsNullRequestAndDetailsThroughConvenienceOverload() throws Exception {
        DSLContext dsl = mock(DSLContext.class, RETURNS_DEEP_STUBS);
        ObjectMapper mapper = mock(ObjectMapper.class);
        when(mapper.writeValueAsString(any())).thenReturn("{}");

        new AuditLogService(dsl, mapper).record(UUID.randomUUID(), "LOGIN", "SESSION",
                UUID.randomUUID(), null, null);

        verify(mapper).writeValueAsString(Map.of());
    }

    @Test
    void fallsBackToEmptyJsonWhenDetailsCannotBeSerialized() throws Exception {
        DSLContext dsl = mock(DSLContext.class, RETURNS_DEEP_STUBS);
        ObjectMapper mapper = mock(ObjectMapper.class);
        when(mapper.writeValueAsString(any())).thenThrow(mock(JsonProcessingException.class));

        assertThatCode(() -> new AuditLogService(dsl, mapper).record(UUID.randomUUID(), "UPDATE",
                "PROJECT", UUID.randomUUID(), Map.of("bad", new Object()), null)).doesNotThrowAnyException();
        verify(dsl).insertInto(AUDIT_LOGS);
    }

    @Test
    void auditStorageFailureNeverBreaksBusinessRequest() {
        DSLContext dsl = mock(DSLContext.class);
        when(dsl.insertInto(AUDIT_LOGS)).thenThrow(new IllegalStateException("database unavailable"));

        assertThatCode(() -> new AuditLogService(dsl, new ObjectMapper()).record(UUID.randomUUID(),
                "UPDATE", "PROJECT", UUID.randomUUID(), Map.of(), null)).doesNotThrowAnyException();
    }
}
