package cn.rvport.backend.source.deploy;

import static org.assertj.core.api.Assertions.assertThat;

import cn.rvport.backend.task.TaskStatus;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;
import org.jooq.JSONB;
import org.junit.jupiter.api.Test;

class SourceDeployResponseTests {

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    void mapsCurrentDeploymentAndParsesSummary() {
        SourceDeployRunView view = run(JSONB.valueOf("{\"files\":3}"), 4L);

        SourceDeployResponse response = SourceDeployResponse.from(view, null, null, objectMapper, 4L);

        assertThat(response.currentEnvironmentConfigVersion()).isEqualTo(4L);
        assertThat(response.currentRuntimeEnvironment()).isTrue();
        assertThat(response.summary()).containsEntry("files", 3);
        assertThat(SourceDeployResponse.from(view, objectMapper).currentRuntimeEnvironment()).isFalse();
        assertThat(SourceDeployResponse.from(view, null, null, objectMapper).summary()).containsEntry("files", 3);
    }

    @Test
    void treatsMissingBlankMalformedAndNullVersionSummariesAsEmpty() {
        assertThat(SourceDeployResponse.from(run(null, null), objectMapper).summary()).isEmpty();
        assertThat(SourceDeployResponse.from(run(JSONB.valueOf(""), 1L), objectMapper).summary()).isEmpty();
        assertThat(SourceDeployResponse.from(run(JSONB.valueOf("   "), 1L), objectMapper).summary()).isEmpty();
        assertThat(SourceDeployResponse.from(run(JSONB.valueOf("not-json"), 1L), objectMapper).summary()).isEmpty();
        assertThat(SourceDeployResponse.from(run(JSONB.valueOf("{}"), null), null, null, objectMapper, 0L)
                .currentRuntimeEnvironment()).isFalse();
        assertThat(new SourceDeployExecutionRequest(
                UUID.randomUUID(), UUID.randomUUID(), null, UUID.randomUUID(), UUID.randomUUID(), null,
                null, false, null).environmentConfigVersionValue()).isZero();
        assertThat(new SourceDeployExecutionRequest(
                UUID.randomUUID(), UUID.randomUUID(), null, UUID.randomUUID(), UUID.randomUUID(), 8L,
                null, false, null).environmentConfigVersionValue()).isEqualTo(8L);
    }

    private SourceDeployRunView run(JSONB summary, Long version) {
        return new SourceDeployRunView(UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(),
                UUID.randomUUID(), version, "/workspace/source", SourceDeployStrategy.TAR_OVER_SSH, false,
                TaskStatus.SUCCEEDED, 3, 20L, 0, summary, OffsetDateTime.now(), OffsetDateTime.now(),
                OffsetDateTime.now());
    }
}
