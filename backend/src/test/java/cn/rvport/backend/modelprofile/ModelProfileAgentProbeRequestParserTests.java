package cn.rvport.backend.modelprofile;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.common.error.ApiException;
import java.util.UUID;
import java.util.stream.Collectors;
import java.util.stream.IntStream;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

class ModelProfileAgentProbeRequestParserTests {

    private final JsonMapper json = JsonMapper.builder().build();
    private final ModelProfileAgentProbeRequestParser parser = new ModelProfileAgentProbeRequestParser();

    @Test
    void parsesOneOrMoreDistinctRuntimeIds() throws Exception {
        UUID first = UUID.randomUUID();
        UUID second = UUID.randomUUID();
        ModelProfileAgentProbeRequest request = parser.parse(node(
                "{\"agentRuntimeIds\":[\"" + first + "\",\"" + second + "\"]}"));
        assertThat(request.agentRuntimeIds()).containsExactly(first, second);
    }

    @Test
    void rejectsInvalidEnvelopeAndFieldShape() throws Exception {
        assertInvalid(null, "请求体必须是 JSON object");
        assertInvalid(node("[]"), "请求体必须是 JSON object");
        assertInvalid(node("{\"unknown\":[]}"), "请求包含不可写字段: unknown");
        assertInvalid(node("{}"), "agentRuntimeIds 必须是 UUID array");
        assertInvalid(node("{\"agentRuntimeIds\":null}"), "agentRuntimeIds 必须是 UUID array");
        assertInvalid(node("{\"agentRuntimeIds\":\"id\"}"), "agentRuntimeIds 必须是 UUID array");
    }

    @Test
    void rejectsNonTextMalformedDuplicateAndEmptyIds() throws Exception {
        UUID id = UUID.randomUUID();
        assertInvalid(node("{\"agentRuntimeIds\":[1]}"), "agentRuntimeIds 必须是 UUID array");
        assertInvalid(node("{\"agentRuntimeIds\":[\"bad\"]}"), "agentRuntimeIds 必须是 UUID array");
        assertInvalid(node("{\"agentRuntimeIds\":[\"" + id + "\",\"" + id + "\"]}"),
                "agentRuntimeIds 不能重复");
        assertInvalid(node("{\"agentRuntimeIds\":[]}"), "agentRuntimeIds 不能为空");
    }

    @Test
    void rejectsMoreThanTenRuntimeIds() throws Exception {
        String ids = IntStream.range(0, 11).mapToObj(ignored -> "\"" + UUID.randomUUID() + "\"")
                .collect(Collectors.joining(","));
        assertInvalid(node("{\"agentRuntimeIds\":[" + ids + "]}"), "agentRuntimeIds 不能超过 10 个");
    }

    private JsonNode node(String value) throws Exception {
        return json.readTree(value);
    }

    private void assertInvalid(JsonNode body, String message) {
        assertThatThrownBy(() -> parser.parse(body)).isInstanceOf(ApiException.class).hasMessage(message);
    }
}
