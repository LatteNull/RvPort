package cn.rvport.backend.buildvalidation;

import static org.assertj.core.api.Assertions.assertThat;

import cn.rvport.backend.jooq.tables.records.BuildRunsRecord;
import cn.rvport.backend.source.SourceRevisionResponse;
import cn.rvport.backend.source.SourceRevisionType;
import cn.rvport.backend.task.TaskStatus;
import java.time.OffsetDateTime;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class BuildValidationValueObjectTests {

    @Test
    void listRequestNormalizesPagingAndCurrentContextModes() {
        UUID activeRevisionId = UUID.randomUUID();
        BuildValidationListRequest defaults = request(null, null, null, null, null);
        assertThat(defaults.normalizedPage()).isEqualTo(1);
        assertThat(defaults.normalizedPageSize()).isEqualTo(20);
        assertThat(defaults.effectiveCurrentOnly()).isTrue();
        BuildValidationListRequest current = defaults.withCurrentContext(activeRevisionId, 7L);
        assertThat(current.sourceRevisionId()).isEqualTo(activeRevisionId);
        assertThat(current.environmentConfigVersion()).isEqualTo(7L);

        UUID retainedRevisionId = UUID.randomUUID();
        BuildValidationListRequest explicitCurrent = request(1, 20, retainedRevisionId, 5L, true)
                .withCurrentContext(activeRevisionId, 7L);
        assertThat(explicitCurrent.effectiveCurrentOnly()).isTrue();
        assertThat(explicitCurrent.sourceRevisionId()).isEqualTo(retainedRevisionId);
        assertThat(explicitCurrent.environmentConfigVersion()).isEqualTo(5L);

        UUID explicitRevisionId = UUID.randomUUID();
        BuildValidationListRequest explicit = request(2, 50, explicitRevisionId, 3L, false);
        assertThat(explicit.normalizedPage()).isEqualTo(2);
        assertThat(explicit.normalizedPageSize()).isEqualTo(50);
        assertThat(explicit.effectiveCurrentOnly()).isFalse();
        assertThat(explicit.withCurrentContext(activeRevisionId, 7L)).isSameAs(explicit);

        BuildValidationListRequest includeStale = new BuildValidationListRequest(
                1, 20, null, null, null, true, true, null, null, null, null, null, null);
        assertThat(includeStale.effectiveCurrentOnly()).isFalse();
    }

    @Test
    void responseReportsEveryStalenessCombinationAndCompileDatabaseShape() {
        UUID projectId = UUID.randomUUID();
        BuildValidationRunView currentRun = run(projectId, 4L, Map.of(
                "compileDatabase", Map.of("available", true, "commandCount", 2)));
        SourceRevisionResponse active = revision(currentRun.sourceRevisionId(), projectId, true);

        BuildValidationResponse current = BuildValidationResponse.from(currentRun, active, null, 4L);
        assertThat(current.currentSourceRevision()).isTrue();
        assertThat(current.currentRuntimeEnvironment()).isTrue();
        assertThat(current.staleReasons()).isEmpty();
        assertThat(current.compileDatabase()).containsEntry("available", true).containsEntry("commandCount", 2);
        assertThat(current.bitcode()).containsEntry("status", "NOT_ATTEMPTED")
                .containsEntry("reasonCode", "LEGACY_RECORD");

        Map<String, Object> bitcodeFacts = new java.util.LinkedHashMap<>();
        bitcodeFacts.put("available", true);
        bitcodeFacts.put("status", "READY");
        bitcodeFacts.put("succeededCount", 2);
        bitcodeFacts.put("artifactSetId", null);
        BuildValidationRunView bitcodeRun = run(projectId, 4L, Map.of("bitcode", bitcodeFacts));
        BuildValidationResponse withBitcode = BuildValidationResponse.from(bitcodeRun, active, null, 4L);
        assertThat(withBitcode.bitcode()).containsEntry("available", true)
                .containsEntry("status", "READY").containsEntry("succeededCount", 2)
                .containsEntry("artifactSetId", null);

        BuildValidationResponse bothStale = BuildValidationResponse.from(
                run(projectId, null, null), revision(currentRun.sourceRevisionId(), projectId, false), null, 4L,
                "full script", "summary");
        assertThat(bothStale.staleReasons()).containsExactly(
                "SOURCE_REVISION_CHANGED", "RUNTIME_ENVIRONMENT_CHANGED");
        assertThat(bothStale.compileDatabase()).containsEntry("available", false);
        assertThat(bothStale.command()).isEqualTo("full script");

        Map<String, Object> invalidFacts = new HashMap<>();
        invalidFacts.put("compileDatabase", "not-a-map");
        BuildValidationResponse onlyRuntimeStale = BuildValidationResponse.from(
                run(projectId, 3L, invalidFacts), active, null, 4L);
        assertThat(onlyRuntimeStale.staleReasons()).containsExactly("RUNTIME_ENVIRONMENT_CHANGED");
        assertThat(onlyRuntimeStale.compileDatabase()).containsEntry("available", false);

        BuildValidationResponse onlySourceStale = BuildValidationResponse.from(
                currentRun, null, null, 4L);
        assertThat(onlySourceStale.staleReasons()).containsExactly("SOURCE_REVISION_CHANGED");
    }

    @Test
    void runViewMappingDefaultsNullCollectionsAndScope() {
        BuildRunsRecord record = new BuildRunsRecord();
        UUID id = UUID.randomUUID();
        record.setId(id);
        record.setProjectId(UUID.randomUUID());
        record.setTaskId(UUID.randomUUID());
        record.setSourceRevisionId(UUID.randomUUID());
        record.setEnvironmentId(UUID.randomUUID());
        record.setStatus(TaskStatus.PENDING.name());
        record.setCreatedAt(OffsetDateTime.now());

        BuildValidationRunView view = BuildValidationRunView.from(record, null, null, null);

        assertThat(view.id()).isEqualTo(id);
        assertThat(view.buildScope()).isEqualTo(BuildValidationScope.BOTH);
        assertThat(view.environmentVariables()).isEmpty();
        assertThat(view.buildFacts()).isEmpty();
        assertThat(view.resource()).containsEntry("type", "BUILD_VALIDATION").containsEntry("id", id);
    }

    private BuildValidationListRequest request(
            Integer page, Integer pageSize, UUID revisionId, Long environmentVersion, Boolean currentOnly
    ) {
        return new BuildValidationListRequest(page, pageSize, revisionId, null, environmentVersion, currentOnly,
                false, null, null, null, null, null, null);
    }

    private BuildValidationRunView run(UUID projectId, Long environmentVersion, Map<String, Object> facts) {
        return new BuildValidationRunView(
                UUID.randomUUID(), projectId, UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(),
                BuildValidationScope.BOTH, UUID.randomUUID(), environmentVersion, UUID.randomUUID(), "hash",
                "make", "/workspace", 60, 0, TaskStatus.SUCCEEDED, null, null, null, null,
                OffsetDateTime.now(), OffsetDateTime.now(), OffsetDateTime.now(), Map.of(), facts);
    }

    private SourceRevisionResponse revision(UUID id, UUID projectId, boolean active) {
        return new SourceRevisionResponse(id, projectId, SourceRevisionType.ARCHIVE, "v1", "source.zip",
                null, null, null, null, active, UUID.randomUUID(), OffsetDateTime.now());
    }
}
