package cn.rvport.backend.dependency;

import static org.assertj.core.api.Assertions.assertThat;

import cn.rvport.backend.task.TaskStatus;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class DependencyAnalysisValueObjectTests {

    @Test
    void listRequestNormalizesDefaultsExplicitValuesAndCurrentContext() {
        UUID revisionId = UUID.randomUUID();
        DependencyAnalysisListRequest defaults = request(null, null, null, null, null, null);
        assertThat(defaults.normalizedPage()).isEqualTo(1);
        assertThat(defaults.normalizedPageSize()).isEqualTo(20);
        assertThat(defaults.effectiveCurrentOnly()).isTrue();
        DependencyAnalysisListRequest current = defaults.withCurrentContext(revisionId, 8L);
        assertThat(current.sourceRevisionId()).isEqualTo(revisionId);
        assertThat(current.environmentConfigVersion()).isEqualTo(8L);

        DependencyAnalysisListRequest explicit = request(2, 50, revisionId, 4L, false, false);
        assertThat(explicit.normalizedPage()).isEqualTo(2);
        assertThat(explicit.normalizedPageSize()).isEqualTo(50);
        assertThat(explicit.effectiveCurrentOnly()).isFalse();
        assertThat(explicit.withCurrentContext(UUID.randomUUID(), 9L)).isSameAs(explicit);

        DependencyAnalysisListRequest includeStale = request(1, 20, null, null, true, true);
        assertThat(includeStale.effectiveCurrentOnly()).isFalse();

        DependencyAnalysisListRequest explicitCurrent = request(1, 20, revisionId, 4L, true, false);
        assertThat(explicitCurrent.effectiveCurrentOnly()).isTrue();
        DependencyAnalysisListRequest unchangedContext = explicitCurrent.withCurrentContext(UUID.randomUUID(), 9L);
        assertThat(unchangedContext.sourceRevisionId()).isEqualTo(revisionId);
        assertThat(unchangedContext.environmentConfigVersion()).isEqualTo(4L);
    }

    @Test
    void responseReportsAllSourceAndEnvironmentStalenessCombinations() {
        UUID projectId = UUID.randomUUID();
        DependencyAnalysisView current = run(projectId, 5L);

        assertThat(DependencyAnalysisResponse.from(current, 5L, true).staleReasons()).isEmpty();
        assertThat(DependencyAnalysisResponse.from(current, 4L, true).staleReasons())
                .containsExactly("RUNTIME_ENVIRONMENT_CHANGED");
        assertThat(DependencyAnalysisResponse.from(current, 5L, false).staleReasons())
                .containsExactly("SOURCE_REVISION_CHANGED");
        assertThat(DependencyAnalysisResponse.from(run(projectId, null), 5L).staleReasons())
                .containsExactly("SOURCE_REVISION_CHANGED", "RUNTIME_ENVIRONMENT_CHANGED");
    }

    private DependencyAnalysisListRequest request(
            Integer page, Integer pageSize, UUID revisionId, Long environmentVersion,
            Boolean currentOnly, Boolean includeStale
    ) {
        return new DependencyAnalysisListRequest(page, pageSize, revisionId, environmentVersion, currentOnly,
                includeStale, null, null, null, null, null, null);
    }

    private DependencyAnalysisView run(UUID projectId, Long environmentVersion) {
        return new DependencyAnalysisView(UUID.randomUUID(), projectId, UUID.randomUUID(), UUID.randomUUID(),
                UUID.randomUUID(), UUID.randomUUID(), environmentVersion, TaskStatus.SUCCEEDED, Map.of(), List.of(),
                OffsetDateTime.now(), OffsetDateTime.now(), OffsetDateTime.now());
    }
}
