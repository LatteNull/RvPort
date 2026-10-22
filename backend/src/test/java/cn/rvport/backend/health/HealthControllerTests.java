package cn.rvport.backend.health;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;

import cn.rvport.backend.common.web.TraceIdFilter;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

class HealthControllerTests {

    @Test
    void returnsHealthEnvelope() throws Exception {
        MockMvc mockMvc = MockMvcBuilders.standaloneSetup(new HealthController())
                .addFilter(new TraceIdFilter())
                .build();
        MvcResult result = mockMvc.perform(get("/api/health")).andReturn();
        String body = result.getResponse().getContentAsString();

        assertThat(result.getResponse().getStatus()).isBetween(200, 299);
        assertThat(result.getResponse().getHeader("X-Trace-Id")).isNotBlank();
        assertThat(body)
                .contains("\"status\":\"UP\"")
                .contains("\"traceId\"")
                .contains("\"timestamp\"");
    }

    @Test
    void preservesCallerTraceId() throws Exception {
        MockMvc mockMvc = MockMvcBuilders.standaloneSetup(new HealthController())
                .addFilter(new TraceIdFilter())
                .build();

        MvcResult result = mockMvc.perform(get("/health").header(TraceIdFilter.TRACE_ID_HEADER, "trace-123"))
                .andReturn();

        assertThat(result.getResponse().getHeader(TraceIdFilter.TRACE_ID_HEADER)).isEqualTo("trace-123");
        assertThat(result.getResponse().getContentAsString()).contains("\"traceId\":\"trace-123\"");
    }

    @Test
    void replacesBlankCallerTraceId() throws Exception {
        MockMvc mockMvc = MockMvcBuilders.standaloneSetup(new HealthController())
                .addFilter(new TraceIdFilter())
                .build();

        MvcResult result = mockMvc.perform(get("/health").header(TraceIdFilter.TRACE_ID_HEADER, "   "))
                .andReturn();

        assertThat(result.getResponse().getHeader(TraceIdFilter.TRACE_ID_HEADER))
                .isNotBlank().isNotEqualTo("   ");
    }
}
