package cn.rvport.backend.workflow;

import cn.rvport.backend.project.runtime.ProjectRuntimeEnvironmentService;
import cn.rvport.backend.source.SourceRepository;
import cn.rvport.backend.source.SourceRevisionView;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ProjectContextService {

    private final SourceRepository sourceRepository;
    private final ProjectRuntimeEnvironmentService runtimeEnvironmentService;

    public ProjectContextService(
            SourceRepository sourceRepository,
            ProjectRuntimeEnvironmentService runtimeEnvironmentService
    ) {
        this.sourceRepository = sourceRepository;
        this.runtimeEnvironmentService = runtimeEnvironmentService;
    }

    @Transactional(readOnly = true)
    public ProjectContextSnapshot snapshot(UUID projectId) {
        UUID sourceRevisionId = sourceRepository.findActive(projectId)
                .map(SourceRevisionView::id)
                .orElse(null);
        return new ProjectContextSnapshot(sourceRevisionId, runtimeEnvironmentService.currentVersion(projectId));
    }
}
