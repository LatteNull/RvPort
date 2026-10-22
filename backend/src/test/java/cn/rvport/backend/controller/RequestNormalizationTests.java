package cn.rvport.backend.controller;

import static org.assertj.core.api.Assertions.assertThat;

import cn.rvport.backend.buildvalidation.BuildValidationListRequest;
import cn.rvport.backend.dependency.DependencyAnalysisListRequest;
import cn.rvport.backend.kb.KbScanListRequest;
import cn.rvport.backend.source.SourceListRequest;
import cn.rvport.backend.task.TaskListRequest;
import cn.rvport.backend.user.AdminUserListRequest;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class RequestNormalizationTests {

    @Test
    void simpleListRequestsUseDefaultsAndPreserveExplicitPages() {
        assertDefaults(new SourceListRequest(null, null, null, null).normalizedPage(),
                new SourceListRequest(null, null, null, null).normalizedPageSize());
        assertDefaults(new AdminUserListRequest(null, null, null, null).normalizedPage(),
                new AdminUserListRequest(null, null, null, null).normalizedPageSize());
        assertDefaults(new TaskListRequest(null, null, null, null).normalizedPage(),
                new TaskListRequest(null, null, null, null).normalizedPageSize());

        assertThat(new SourceListRequest(null, null, 3, 40).normalizedPage()).isEqualTo(3);
        assertThat(new AdminUserListRequest(4, 50, null, null).normalizedPageSize()).isEqualTo(50);
        assertThat(new TaskListRequest(null, null, 5, 60).normalizedPageSize()).isEqualTo(60);
    }

    @Test
    void buildRequestAppliesCurrentContextUnlessStaleWasRequested() {
        UUID activeRevision = UUID.randomUUID();
        BuildValidationListRequest defaults = new BuildValidationListRequest(
                null, null, null, null, null, null, null, null, null, null, null, null, null);
        BuildValidationListRequest current = defaults.withCurrentContext(activeRevision, 7L);
        BuildValidationListRequest stale = new BuildValidationListRequest(
                2, 30, null, null, null, null, true, null, null, null, null, null, null);

        assertDefaults(defaults.normalizedPage(), defaults.normalizedPageSize());
        assertThat(defaults.effectiveCurrentOnly()).isTrue();
        assertThat(current.sourceRevisionId()).isEqualTo(activeRevision);
        assertThat(current.environmentConfigVersion()).isEqualTo(7L);
        assertThat(stale.effectiveCurrentOnly()).isFalse();
        assertThat(stale.withCurrentContext(activeRevision, 8L)).isSameAs(stale);
    }

    @Test
    void dependencyRequestPreservesExplicitContextAndSupportsCurrentOptOut() {
        UUID explicitRevision = UUID.randomUUID();
        DependencyAnalysisListRequest request = new DependencyAnalysisListRequest(
                2, 30, explicitRevision, 9L, false, false, null, null, null, null, null, null);
        DependencyAnalysisListRequest result = request.withCurrentContext(UUID.randomUUID(), 10L);
        DependencyAnalysisListRequest includeStale = new DependencyAnalysisListRequest(
                null, null, null, null, true, true, null, null, null, null, null, null);

        assertThat(request.normalizedPage()).isEqualTo(2);
        assertThat(request.normalizedPageSize()).isEqualTo(30);
        assertThat(request.effectiveCurrentOnly()).isFalse();
        assertThat(result).isSameAs(request);
        assertThat(includeStale.effectiveCurrentOnly()).isFalse();

        DependencyAnalysisListRequest defaults = new DependencyAnalysisListRequest(
                null, null, null, null, null, null, null, null, null, null, null, null);
        DependencyAnalysisListRequest current = defaults.withCurrentContext(explicitRevision, 11L);
        assertDefaults(defaults.normalizedPage(), defaults.normalizedPageSize());
        assertThat(current.sourceRevisionId()).isEqualTo(explicitRevision);
        assertThat(current.environmentConfigVersion()).isEqualTo(11L);
    }

    @Test
    void kbRequestUsesActiveRevisionOnlyForCurrentQueries() {
        UUID explicit = UUID.randomUUID();
        KbScanListRequest defaults = new KbScanListRequest(null, null, null, null, null, null, null, null, null);
        KbScanListRequest current = defaults.withCurrentSourceRevision(explicit);
        KbScanListRequest stale = new KbScanListRequest(2, 30, null, null, true, true, null, null, null);
        KbScanListRequest specified = new KbScanListRequest(2, 30, null, explicit, true, false, null, null, null);

        assertDefaults(defaults.normalizedPage(), defaults.normalizedPageSize());
        assertThat(defaults.effectiveCurrentOnly()).isTrue();
        assertThat(current.sourceRevisionId()).isEqualTo(explicit);
        assertThat(stale.effectiveCurrentOnly()).isFalse();
        assertThat(stale.withCurrentSourceRevision(UUID.randomUUID())).isSameAs(stale);
        assertThat(specified.withCurrentSourceRevision(UUID.randomUUID()).sourceRevisionId()).isEqualTo(explicit);
    }

    private void assertDefaults(int page, int pageSize) {
        assertThat(page).isEqualTo(1);
        assertThat(pageSize).isEqualTo(20);
    }
}
