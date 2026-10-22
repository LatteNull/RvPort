package cn.rvport.backend.source;

import static org.assertj.core.api.Assertions.assertThat;

import cn.rvport.backend.project.ProjectSourceInputType;
import cn.rvport.backend.task.TaskStatus;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class SourceValueObjectTests {

    @Test
    void sourceListRequestAppliesDefaultsAndPreservesExplicitPagination() {
        assertThat(new SourceListRequest(null, null, null, null).normalizedPage()).isEqualTo(1);
        assertThat(new SourceListRequest(null, null, null, null).normalizedPageSize()).isEqualTo(20);
        assertThat(new SourceListRequest(SourceRevisionType.GIT, true, 3, 40).normalizedPage()).isEqualTo(3);
        assertThat(new SourceListRequest(SourceRevisionType.GIT, true, 3, 40).normalizedPageSize()).isEqualTo(40);
    }

    @Test
    void responseFactoriesAcceptNullAndMapPresentViews() {
        assertThat(SourceRevisionResponse.from(null)).isNull();
        assertThat(RecheckRunResponse.from(null)).isNull();

        UUID projectId = UUID.randomUUID();
        SourceRevisionView revision = new SourceRevisionView(UUID.randomUUID(), projectId, SourceRevisionType.GIT,
                "v1", null, "https://example.com/repo.git", "main", "abc", null, null, "note", true,
                UUID.randomUUID(), OffsetDateTime.now());
        assertThat(SourceRevisionResponse.from(revision).projectId()).isEqualTo(projectId);

        RecheckRunView recheck = new RecheckRunView(UUID.randomUUID(), projectId, UUID.randomUUID(),
                UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), Map.of("fixed", 1),
                TaskStatus.SUCCEEDED, OffsetDateTime.now());
        assertThat(RecheckRunResponse.from(recheck).summary()).containsEntry("fixed", 1);
    }
}
