package cn.rvport.backend.workflow;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import cn.rvport.backend.project.runtime.ProjectRuntimeEnvironmentService;
import cn.rvport.backend.source.SourceRepository;
import cn.rvport.backend.source.SourceRevisionType;
import cn.rvport.backend.source.SourceRevisionView;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class ProjectContextServiceTests {

    private final SourceRepository sourceRepository = mock(SourceRepository.class);
    private final ProjectRuntimeEnvironmentService environmentService = mock(ProjectRuntimeEnvironmentService.class);
    private final ProjectContextService service = new ProjectContextService(sourceRepository, environmentService);

    @Test
    void snapshotsActiveSourceAndEnvironmentVersion() {
        UUID projectId = UUID.randomUUID();
        SourceRevisionView revision = revision(projectId);
        when(sourceRepository.findActive(projectId)).thenReturn(Optional.of(revision));
        when(environmentService.currentVersion(projectId)).thenReturn(8L);

        assertThat(service.snapshot(projectId))
                .isEqualTo(new ProjectContextSnapshot(revision.id(), 8L));
    }

    @Test
    void snapshotsMissingSourceWithDefaultEnvironmentVersion() {
        UUID projectId = UUID.randomUUID();
        when(sourceRepository.findActive(projectId)).thenReturn(Optional.empty());

        assertThat(service.snapshot(projectId))
                .isEqualTo(new ProjectContextSnapshot(null, 0L));
    }

    private static SourceRevisionView revision(UUID projectId) {
        return new SourceRevisionView(UUID.randomUUID(), projectId, SourceRevisionType.GIT, "v1", null,
                "https://example.test/repo.git", "main", "abc", null, "/runtime/source", null,
                true, UUID.randomUUID(), null);
    }
}
