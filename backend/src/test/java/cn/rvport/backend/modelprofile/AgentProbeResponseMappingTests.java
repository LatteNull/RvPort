package cn.rvport.backend.modelprofile;

import static org.assertj.core.api.Assertions.assertThat;

import cn.rvport.backend.jooq.tables.records.AgentRuntimesRecord;
import cn.rvport.backend.jooq.tables.records.ModelProfileAgentProbeResultsRecord;
import cn.rvport.backend.jooq.tables.records.ModelProfileAgentProbeRunsRecord;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;
import org.jooq.JSONB;
import org.junit.jupiter.api.Test;

class AgentProbeResponseMappingTests {

    @Test
    void mapsRuntimeAndEveryTerminalStatus() {
        AgentRuntimesRecord runtime = new AgentRuntimesRecord();
        runtime.setId(UUID.randomUUID());
        runtime.setAgentType("CODEX");
        runtime.setName("Codex");
        runtime.setEnabled(true);

        assertThat(AgentRuntimeSummaryResponse.from(runtime))
                .extracting(AgentRuntimeSummaryResponse::agentType, AgentRuntimeSummaryResponse::enabled)
                .containsExactly("CODEX", true);
        assertThat(AgentProbeRunStatus.PENDING.terminal()).isFalse();
        assertThat(AgentProbeRunStatus.RUNNING.terminal()).isFalse();
        assertThat(List.of(AgentProbeRunStatus.SUCCESS, AgentProbeRunStatus.PARTIAL_SUCCESS,
                AgentProbeRunStatus.FAILED, AgentProbeRunStatus.TIMEOUT))
                .allMatch(AgentProbeRunStatus::terminal);
    }

    @Test
    void activeRunHandlesNullValidAndBrokenRuntimeJson() {
        assertThat(ActiveAgentProbeRunResponse.from(null)).isNull();
        ModelProfileAgentProbeRunsRecord run = run();
        run.setSelectedAgentRuntimes(JSONB.valueOf("[{\"id\":\"" + UUID.randomUUID()
                + "\",\"agentType\":\"CODEX\",\"name\":\"Codex\",\"enabled\":true}]"));
        assertThat(ActiveAgentProbeRunResponse.from(run).agentRuntimes()).singleElement()
                .extracting(AgentRuntimeSummaryResponse::agentType).isEqualTo("CODEX");

        run.setSelectedAgentRuntimes(null);
        assertThat(ActiveAgentProbeRunResponse.from(run).agentRuntimes()).isEmpty();
        run.setSelectedAgentRuntimes(JSONB.valueOf(" "));
        assertThat(ActiveAgentProbeRunResponse.from(run).agentRuntimes()).isEmpty();
        run.setSelectedAgentRuntimes(JSONB.valueOf("not-json"));
        assertThat(ActiveAgentProbeRunResponse.from(run).agentRuntimes()).isEmpty();
    }

    @Test
    void runAndResultMappingsHandleValidEmptyAndMalformedJson() {
        UUID runtimeId = UUID.randomUUID();
        ModelProfileAgentProbeRunsRecord run = run();
        run.setSelectedAgentRuntimeIds(JSONB.valueOf("[\"" + runtimeId + "\"]"));
        run.setSelectedAgentRuntimes(JSONB.valueOf("[]"));
        assertThat(ModelProfileAgentProbeRunResponse.from(run, null).selectedAgentRuntimeIds()).containsExactly(runtimeId);
        assertThat(ModelProfileAgentProbeRunResponse.from(run, null).results()).isEmpty();

        run.setSelectedAgentRuntimeIds(JSONB.valueOf("bad"));
        run.setSelectedAgentRuntimes(JSONB.valueOf("bad"));
        assertThat(ModelProfileAgentProbeRunResponse.from(run, List.of()).selectedAgentRuntimeIds()).isEmpty();
        assertThat(ModelProfileAgentProbeRunResponse.from(run, List.of()).agentRuntimes()).isEmpty();

        ModelProfileAgentProbeResultsRecord result = new ModelProfileAgentProbeResultsRecord();
        result.setChecks(JSONB.valueOf("[{\"name\":\"basic\",\"passed\":true}]"));
        result.setDetails(JSONB.valueOf("{\"latencyMs\":12}"));
        assertThat(ModelProfileAgentProbeResultResponse.from(result).checks()).singleElement()
                .satisfies(check -> assertThat(check).containsEntry("name", "basic"));
        assertThat(ModelProfileAgentProbeResultResponse.from(result).details()).containsEntry("latencyMs", 12);

        result.setChecks(null);
        result.setDetails(JSONB.valueOf("bad"));
        assertThat(ModelProfileAgentProbeResultResponse.from(result).checks()).isEmpty();
        assertThat(ModelProfileAgentProbeResultResponse.from(result).details()).isEmpty();

        result.setChecks(JSONB.valueOf(" "));
        result.setDetails(JSONB.valueOf(" "));
        assertThat(ModelProfileAgentProbeResultResponse.from(result).checks()).isEmpty();
        assertThat(ModelProfileAgentProbeResultResponse.from(result).details()).isEmpty();
    }

    private ModelProfileAgentProbeRunsRecord run() {
        ModelProfileAgentProbeRunsRecord run = new ModelProfileAgentProbeRunsRecord();
        run.setId(UUID.randomUUID());
        run.setModelProfileId(UUID.randomUUID());
        run.setStatus("RUNNING");
        run.setCreatedAt(OffsetDateTime.now());
        return run;
    }
}
