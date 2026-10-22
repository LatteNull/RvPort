package cn.rvport.backend.common.error;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.BindingResult;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.context.request.async.AsyncRequestNotUsableException;
import org.springframework.web.multipart.MaxUploadSizeExceededException;
import org.springframework.web.multipart.MultipartException;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.resource.NoResourceFoundException;

class GlobalExceptionHandlerTests {

    private final GlobalExceptionHandler handler = new GlobalExceptionHandler();

    @ParameterizedTest
    @ValueSource(strings = {"/unit/unknown-route", "/unit/missing-resource"})
    void missingRoutesAndResourcesUse404WithoutLeakingExceptionDetails(String path) throws Exception {
        var mvc = MockMvcBuilders.standaloneSetup(new MissingResourceController())
                .setControllerAdvice(handler).build();

        var result = mvc.perform(get(path))
                .andExpect(status().isNotFound())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.code").value("RESOURCE_NOT_FOUND"))
                .andExpect(jsonPath("$.message").value("请求的资源不存在"))
                .andExpect(jsonPath("$.details").isEmpty())
                .andReturn();

        assertThat(result.getResponse().getContentAsString())
                .doesNotContain("/private/server", "NoResourceFoundException");
    }

    @Test
    void missingResourceKeeps404AndErrorEventForSseClients() throws Exception {
        var mvc = MockMvcBuilders.standaloneSetup(new MissingResourceController())
                .setControllerAdvice(handler).build();

        var result = mvc.perform(get("/unit/missing-resource").accept(MediaType.TEXT_EVENT_STREAM))
                .andExpect(status().isNotFound())
                .andExpect(content().contentTypeCompatibleWith(MediaType.TEXT_EVENT_STREAM))
                .andReturn();

        assertThat(result.getResponse().getContentAsString())
                .startsWith("event: error\ndata: ")
                .contains("\"code\":\"RESOURCE_NOT_FOUND\"")
                .doesNotContain("/private/server").endsWith("\n\n");
    }

    @RestController
    static class MissingResourceController {
        @GetMapping("/unit/missing-resource")
        public void missingResource() throws NoResourceFoundException {
            var exception = mock(NoResourceFoundException.class);
            when(exception.getMessage()).thenReturn("/private/server/internal-resource");
            throw exception;
        }
    }

    @Test
    void rendersApiErrorsAsJsonOrSseAccordingToAcceptHeader() {
        ApiException exception = new ApiException(
                HttpStatus.CONFLICT, "CONFLICT", "conflict", Map.of("id", 1));
        HttpServletRequest json = request(null);
        ResponseEntity<?> jsonResponse = handler.handleApiException(exception, json);
        assertThat(jsonResponse.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
        assertThat(jsonResponse.getHeaders().getContentType()).isEqualTo(MediaType.APPLICATION_JSON);
        assertThat(jsonResponse.getBody()).isInstanceOf(ApiErrorResponse.class);

        ResponseEntity<?> htmlResponse = handler.handleApiException(exception, request("text/html"));
        assertThat(htmlResponse.getHeaders().getContentType()).isEqualTo(MediaType.APPLICATION_JSON);

        HttpServletRequest sse = request("text/html, text/event-stream");
        ResponseEntity<?> sseResponse = handler.handleApiException(exception, sse);
        assertThat(sseResponse.getHeaders().getContentType()).isEqualTo(MediaType.TEXT_EVENT_STREAM);
        assertThat(sseResponse.getBody().toString()).startsWith("event: error\ndata: ")
                .contains("\"code\":\"CONFLICT\"").endsWith("\n\n");
    }

    @Test
    void mapsValidationErrorsIncludingMissingDefaultMessage() {
        BindingResult binding = mock(BindingResult.class);
        when(binding.getFieldErrors()).thenReturn(List.of(
                new FieldError("request", "name", "required"),
                new FieldError("request", "description", null)));
        MethodArgumentNotValidException exception = new MethodArgumentNotValidException(null, binding);

        ResponseEntity<?> response = handler.handleValidation(exception, request(null));

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        ApiErrorResponse body = (ApiErrorResponse) response.getBody();
        assertThat(body.code()).isEqualTo("VALIDATION_ERROR");
        assertThat(body.details()).containsEntry("fields", List.of(
                Map.of("field", "name", "message", "required"),
                Map.of("field", "description", "message", "")));
    }

    @Test
    void mapsUploadMultipartUnexpectedAndDisconnectedAsyncRequests() {
        assertThat(handler.handleMaxUploadSizeExceeded(
                new MaxUploadSizeExceededException(10), request(null)).getStatusCode())
                .isEqualTo(HttpStatus.PAYLOAD_TOO_LARGE);
        assertThat(handler.handleMultipartException(
                new MultipartException("bad"), request(null)).getStatusCode())
                .isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(handler.handleUnexpected(new IllegalStateException("boom"), request(null)).getStatusCode())
                .isEqualTo(HttpStatus.INTERNAL_SERVER_ERROR);
        assertThat(handler.handleAsyncRequestNotUsable(
                new AsyncRequestNotUsableException("closed")).getStatusCode())
                .isEqualTo(HttpStatus.NO_CONTENT);
    }

    @Test
    void usesMinimalSseJsonWhenSerializationFails() throws Exception {
        ObjectMapper mapper = mock(ObjectMapper.class);
        when(mapper.writeValueAsString(org.mockito.ArgumentMatchers.any()))
                .thenThrow(new JsonProcessingException("broken") { });
        ReflectionTestUtils.setField(handler, "objectMapper", mapper);

        ResponseEntity<?> response = handler.handleApiException(
                new ApiException(HttpStatus.BAD_REQUEST, "BAD", "message"), request("text/event-stream"));

        assertThat(response.getBody().toString())
                .contains("{\"code\":\"BAD\",\"message\":\"message\"}");
    }

    private HttpServletRequest request(String accept) {
        HttpServletRequest request = mock(HttpServletRequest.class);
        when(request.getHeader("Accept")).thenReturn(accept);
        when(request.getAttribute(org.slf4j.MDC.class.getName())).thenReturn(null);
        return request;
    }
}
