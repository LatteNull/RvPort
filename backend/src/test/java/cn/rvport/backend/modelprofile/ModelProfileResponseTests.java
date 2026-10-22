package cn.rvport.backend.modelprofile;

import static org.assertj.core.api.Assertions.assertThat;

import cn.rvport.backend.jooq.tables.records.ModelProfileAgentProbeResultsRecord;
import cn.rvport.backend.jooq.tables.records.ModelProfilesRecord;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.OffsetDateTime;
import java.util.UUID;
import org.jooq.JSONB;
import org.junit.jupiter.api.Test;

class ModelProfileResponseTests {

    private final ObjectMapper objectMapper = new ObjectMapper().findAndRegisterModules();

    @Test
    void profileResponseExposesOnlyGenericCompatibilityFields() {
        ModelProfilesRecord record = new ModelProfilesRecord();
        record.setId(UUID.randomUUID());
        record.setName("generic-profile");
        record.setEnabled(true);
        record.setExecutablePath("codex");
        record.setModelProviderType("OPENAI_COMPATIBLE");
        record.setBaseUrl("https://llm.example.com/v1");
        record.setModel("model-a");
        record.setWireApi("RESPONSES");
        record.setTimeoutSeconds(30);
        record.setMaxRuntimeSeconds(1800);
        record.setLastTestBasicAvailable(true);
        record.setLastTestAgentCompatible(true);
        record.setLastTestDetails(JSONB.valueOf("{\"capabilities\":{\"agentCompatible\":true}}"));
        record.setCreatedAt(OffsetDateTime.now());
        record.setUpdatedAt(OffsetDateTime.now());

        JsonNode json = objectMapper.valueToTree(ModelProfileResponse.from(record));

        assertThat(json.path("lastTestAgentCompatible").asBoolean()).isTrue();
        assertThat(json.has("lastTestCompareCompatible")).isFalse();
        assertThat(json.toString()).doesNotContain("testLogCompareCompatible", "kbAiExtensionCompatible");
    }

    @Test
    void probeResultKeepsGenericChecksAndToleratesMalformedDetails() {
        ModelProfileAgentProbeResultsRecord record = new ModelProfileAgentProbeResultsRecord();
        record.setId(UUID.randomUUID());
        record.setRunId(UUID.randomUUID());
        record.setModelProfileId(UUID.randomUUID());
        record.setAgentRuntimeId(UUID.randomUUID());
        record.setAgentType("CODEX");
        record.setStatus("SUCCESS");
        record.setBasicAvailable(true);
        record.setAgentCompatible(true);
        record.setChecks(JSONB.valueOf("[{\"name\":\"AGENT_TEXT\",\"status\":\"SUCCESS\"}]"));
        record.setDetails(JSONB.valueOf("not-json"));
        record.setCreatedAt(OffsetDateTime.now());
        record.setUpdatedAt(OffsetDateTime.now());

        ModelProfileAgentProbeResultResponse response = ModelProfileAgentProbeResultResponse.from(record);
        JsonNode json = objectMapper.valueToTree(response);

        assertThat(response.checks()).hasSize(1);
        assertThat(response.details()).isEmpty();
        assertThat(json.has("testLogCompareCompatible")).isFalse();
        assertThat(json.has("kbAiExtensionCompatible")).isFalse();
    }

    @Test
    void profileResponseHandlesMissingBlankMalformedAndNullJsonData() {
        ModelProfilesRecord record = new ModelProfilesRecord();
        record.setId(UUID.randomUUID());
        record.setEnabled(null);
        record.setTimeoutSeconds(1);
        record.setMaxRuntimeSeconds(10);
        record.setApiKeyEncrypted(" ");
        record.setLastTestDetails(null);
        record.setLastConnectivityDetails(JSONB.valueOf(" "));

        ModelProfileResponse empty = ModelProfileResponse.from(record, null, null);
        assertThat(empty.enabled()).isFalse();
        assertThat(empty.apiKeyConfigured()).isFalse();
        assertThat(empty.apiKeyMasked()).isNull();
        assertThat(empty.lastTestDetails()).isEmpty();
        assertThat(empty.lastConnectivityDetails()).isEmpty();
        assertThat(empty.agentProbeResults()).isEmpty();

        record.setLastTestDetails(JSONB.valueOf("not-json"));
        record.setLastConnectivityDetails(null);
        assertThat(ModelProfileResponse.from(record).lastTestDetails()).isEmpty();
        assertThat(ModelProfileResponse.from(record).lastConnectivityDetails()).isEmpty();
    }
}
