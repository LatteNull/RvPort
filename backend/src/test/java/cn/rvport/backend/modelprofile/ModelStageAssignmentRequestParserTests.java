package cn.rvport.backend.modelprofile;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.common.error.ApiException;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

class ModelStageAssignmentRequestParserTests {

    private final JsonMapper json = JsonMapper.builder().build();
    private final ModelStageAssignmentRequestParser parser = new ModelStageAssignmentRequestParser();

    @Test
    void parsesAssignmentsAndAcceptsEmptyArray() throws Exception {
        UUID profileId = UUID.randomUUID();
        UUID runtimeId = UUID.randomUUID();
        ModelStageAssignmentRequest request = parser.parse(node("""
                {"assignments":[{"stage":"TEST_COMPARISON","modelProfileId":"%s","agentRuntimeId":"%s"}]}
                """.formatted(profileId, runtimeId)));

        assertThat(request.assignments()).singleElement().satisfies(entry -> {
            assertThat(entry.stage()).isEqualTo("TEST_COMPARISON");
            assertThat(entry.modelProfileId()).isEqualTo(profileId);
            assertThat(entry.agentRuntimeId()).isEqualTo(runtimeId);
        });
        assertThat(parser.parse(node("{\"assignments\":[]}" )).assignments()).isEmpty();
    }

    @Test
    void rejectsInvalidEnvelopeAndAssignmentShape() throws Exception {
        assertInvalid(null, "请求体必须是 JSON object");
        assertInvalid(node("[]"), "请求体必须是 JSON object");
        assertInvalid(node("{}"), "assignments 必须是 array");
        assertInvalid(node("{\"assignments\":null}"), "assignments 必须是 array");
        assertInvalid(node("{\"assignments\":[1]}"), "assignment 必须是 object");
        assertInvalid(node("{\"assignments\":[{\"unknown\":1}]}"), "请求包含不可写字段: unknown");
    }

    @Test
    void rejectsMissingBlankAndNonTextStage() throws Exception {
        UUID id = UUID.randomUUID();
        assertInvalid(node("{\"assignments\":[{\"modelProfileId\":\"" + id + "\",\"agentRuntimeId\":\"" + id + "\"}]}"),
                "stage 必须是非空 string");
        assertInvalid(node("{\"assignments\":[{\"stage\":\" \",\"modelProfileId\":\"" + id + "\",\"agentRuntimeId\":\"" + id + "\"}]}"),
                "stage 必须是非空 string");
        assertInvalid(node("{\"assignments\":[{\"stage\":1,\"modelProfileId\":\"" + id + "\",\"agentRuntimeId\":\"" + id + "\"}]}"),
                "stage 必须是非空 string");
    }

    @Test
    void rejectsMissingNonTextAndMalformedUuids() throws Exception {
        UUID id = UUID.randomUUID();
        assertInvalid(node("{\"assignments\":[{\"stage\":\"S\",\"agentRuntimeId\":\"" + id + "\"}]}"),
                "modelProfileId 必须是非空 string");
        assertInvalid(node("{\"assignments\":[{\"stage\":\"S\",\"modelProfileId\":1,\"agentRuntimeId\":\"" + id + "\"}]}"),
                "modelProfileId 必须是非空 string");
        assertInvalid(node("{\"assignments\":[{\"stage\":\"S\",\"modelProfileId\":\"bad\",\"agentRuntimeId\":\"" + id + "\"}]}"),
                "modelProfileId 必须是 UUID");
        assertInvalid(node("{\"assignments\":[{\"stage\":\"S\",\"modelProfileId\":\"" + id + "\",\"agentRuntimeId\":\"bad\"}]}"),
                "agentRuntimeId 必须是 UUID");
    }

    private JsonNode node(String value) throws Exception {
        return json.readTree(value);
    }

    private void assertInvalid(JsonNode body, String message) {
        assertThatThrownBy(() -> parser.parse(body)).isInstanceOf(ApiException.class).hasMessage(message);
    }
}
