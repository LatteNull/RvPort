package cn.rvport.backend.optimization;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.project.ProjectAccessService;
import cn.rvport.backend.source.SourceRepository;
import cn.rvport.backend.source.SourceRevisionResponse;
import cn.rvport.backend.source.SourceRevisionView;
import cn.rvport.backend.workflow.DomainLatestResponse;
import cn.rvport.backend.workflow.ProjectContextService;
import cn.rvport.backend.workflow.ProjectContextSnapshot;
import java.util.List;
import java.util.Objects;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class OptimizationCycleService {

    private final OptimizationCycleRepository optimizationCycleRepository;
    private final SourceRepository sourceRepository;
    private final ProjectAccessService projectAccessService;
    private final ProjectContextService projectContextService;

    @Autowired
    public OptimizationCycleService(
            OptimizationCycleRepository optimizationCycleRepository,
            SourceRepository sourceRepository,
            ProjectAccessService projectAccessService,
            ProjectContextService projectContextService
    ) {
        this.optimizationCycleRepository = optimizationCycleRepository;
        this.sourceRepository = sourceRepository;
        this.projectAccessService = projectAccessService;
        this.projectContextService = projectContextService;
    }

    OptimizationCycleService(
            OptimizationCycleRepository optimizationCycleRepository,
            SourceRepository sourceRepository,
            ProjectAccessService projectAccessService
    ) {
        this(optimizationCycleRepository, sourceRepository, projectAccessService, null);
    }

    @Transactional
    public OptimizationCycleResponse createOrReuseActiveCycle(UUID projectId, UUID sourceRevisionId) {
        SourceRevisionView sourceRevision = sourceRepository.findById(sourceRevisionId)
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "SOURCE_REVISION_NOT_FOUND", "源码版本不存在"));
        if (!Objects.equals(sourceRevision.projectId(), projectId)) {
            throw new ApiException(HttpStatus.NOT_FOUND, "SOURCE_REVISION_NOT_FOUND", "源码版本不存在");
        }
        OptimizationCycleView cycle = optimizationCycleRepository.createOrReactivate(projectId, sourceRevisionId);
        return response(cycle, sourceRevision);
    }

    @Transactional(readOnly = true)
    public OptimizationOverviewResponse overview(UUID projectId, UUID actorUserId, boolean superAdmin) {
        projectAccessService.requireProjectAccess(projectId, actorUserId, superAdmin);
        long total = optimizationCycleRepository.count(projectId, new OptimizationCycleListRequest(
                1, 1, null, null, null, null, null, null
        ));
        OptimizationCycleResponse current = optimizationCycleRepository.findActive(projectId)
                .map(cycle -> response(cycle, requireSource(cycle.sourceRevisionId())))
                .orElse(null);
        return new OptimizationOverviewResponse(current, total);
    }

    @Transactional(readOnly = true)
    public PageResponse<OptimizationCycleResponse> list(
            UUID projectId,
            OptimizationCycleListRequest request,
            UUID actorUserId,
            boolean superAdmin
    ) {
        projectAccessService.requireProjectAccess(projectId, actorUserId, superAdmin);
        int page = request.normalizedPage();
        int pageSize = request.normalizedPageSize();
        try {
            long total = optimizationCycleRepository.count(projectId, request);
            List<OptimizationCycleResponse> items = optimizationCycleRepository.list(projectId, request)
                    .stream()
                    .map(cycle -> response(cycle, requireSource(cycle.sourceRevisionId())))
                    .toList();
            return PageResponse.of(items, page, pageSize, total);
        } catch (IllegalArgumentException ex) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "OPTIMIZATION_CYCLE_QUERY_INVALID", "优化轮次查询参数不正确");
        }
    }

    @Transactional(readOnly = true)
    public OptimizationCycleResponse get(UUID projectId, UUID cycleId, UUID actorUserId, boolean superAdmin) {
        projectAccessService.requireProjectAccess(projectId, actorUserId, superAdmin);
        OptimizationCycleView cycle = optimizationCycleRepository.findById(cycleId)
                .orElseThrow(() -> notFound());
        if (!Objects.equals(cycle.projectId(), projectId)) {
            throw notFound();
        }
        return response(cycle, requireSource(cycle.sourceRevisionId()));
    }

    @Transactional(readOnly = true)
    public DomainLatestResponse<OptimizationCycleResponse> latest(UUID projectId, UUID actorUserId, boolean superAdmin) {
        projectAccessService.requireProjectAccess(projectId, actorUserId, superAdmin);
        ProjectContextSnapshot context = projectContextService.snapshot(projectId);
        return optimizationCycleRepository.findLatest(projectId, context.sourceRevisionId())
                .map(cycle -> DomainLatestResponse.current(context, null, response(cycle, requireSource(cycle.sourceRevisionId()))))
                .orElseGet(() -> optimizationCycleRepository.findLatest(projectId, null)
                        .map(cycle -> DomainLatestResponse.stale(context, null, response(cycle, requireSource(cycle.sourceRevisionId()))))
                        .orElseGet(() -> DomainLatestResponse.empty(context)));
    }

    private OptimizationCycleResponse response(OptimizationCycleView cycle, SourceRevisionView sourceRevision) {
        SourceRevisionView previous = sourceRepository.findPrevious(cycle.projectId(), sourceRevision.id(), sourceRevision.createdAt())
                .orElse(null);
        return new OptimizationCycleResponse(
                cycle.id(),
                cycle.projectId(),
                cycle.sourceRevisionId(),
                SourceRevisionResponse.from(sourceRevision),
                cycle.cycleNumber(),
                cycle.status(),
                cycle.startedAt(),
                cycle.completedAt(),
                cycle.createdAt(),
                cycle.updatedAt(),
                optimizationCycleRepository.summary(cycle.projectId(), cycle.sourceRevisionId(), previous == null ? null : previous.id())
        );
    }

    private SourceRevisionView requireSource(UUID sourceRevisionId) {
        return sourceRepository.findById(sourceRevisionId)
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "SOURCE_REVISION_NOT_FOUND", "源码版本不存在"));
    }

    private ApiException notFound() {
        return new ApiException(HttpStatus.NOT_FOUND, "OPTIMIZATION_CYCLE_NOT_FOUND", "优化轮次不存在");
    }
}
