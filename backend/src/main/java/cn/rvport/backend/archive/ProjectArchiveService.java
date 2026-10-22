package cn.rvport.backend.archive;

import cn.rvport.backend.artifact.StoredArtifactResource;
import cn.rvport.backend.artifact.StoredArtifactService;
import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.project.ProjectAccessService;
import cn.rvport.backend.source.SourceRepository;
import cn.rvport.backend.source.SourceRevisionResponse;
import cn.rvport.backend.source.SourceRevisionView;
import cn.rvport.backend.task.RvPortTaskTypes;
import cn.rvport.backend.task.TaskCreateCommand;
import cn.rvport.backend.task.TaskRepository;
import cn.rvport.backend.task.TaskResponse;
import cn.rvport.backend.task.TaskService;
import cn.rvport.backend.workflow.DomainLatestExecutionResponse;
import cn.rvport.backend.workflow.DomainLatestResponse;
import cn.rvport.backend.workflow.ProjectContextService;
import cn.rvport.backend.workflow.ProjectContextSnapshot;
import cn.rvport.backend.workflow.StageIds;
import cn.rvport.backend.workflow.StagePrerequisiteKeys;
import cn.rvport.backend.workflow.StageReadinessService;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ProjectArchiveService {

    private final ProjectArchiveRepository archiveRepository;
    private final ArchiveCandidateService candidateService;
    private final SourceRepository sourceRepository;
    private final ProjectAccessService projectAccessService;
    private final TaskService taskService;
    private final TaskRepository taskRepository;
    private final ProjectContextService projectContextService;
    private final StageReadinessService stageReadinessService;
    private final StoredArtifactService storedArtifactService;
    private final ObjectMapper objectMapper;

    @Autowired
    public ProjectArchiveService(
            ProjectArchiveRepository archiveRepository,
            ArchiveCandidateService candidateService,
            SourceRepository sourceRepository,
            ProjectAccessService projectAccessService,
            TaskService taskService,
            TaskRepository taskRepository,
            ProjectContextService projectContextService,
            StageReadinessService stageReadinessService,
            StoredArtifactService storedArtifactService,
            ObjectMapper objectMapper
    ) {
        this.archiveRepository = archiveRepository;
        this.candidateService = candidateService;
        this.sourceRepository = sourceRepository;
        this.projectAccessService = projectAccessService;
        this.taskService = taskService;
        this.taskRepository = taskRepository;
        this.projectContextService = projectContextService;
        this.stageReadinessService = stageReadinessService;
        this.storedArtifactService = storedArtifactService;
        this.objectMapper = objectMapper;
    }

    @Transactional
    public ProjectArchiveCreateResponse createCurrent(UUID projectId, UUID actorUserId, boolean superAdmin) {
        projectAccessService.requireProjectAccess(projectId, actorUserId, superAdmin);
        if (stageReadinessService != null) {
            stageReadinessService.requireSatisfied(
                    projectId,
                    StageIds.ARCHIVE,
                    List.of(StagePrerequisiteKeys.ARCHIVE_CANDIDATES),
                    actorUserId,
                    superAdmin
            );
        }
        SourceRevisionView active = sourceRepository.findActive(projectId)
                .orElseThrow(() -> new ApiException(HttpStatus.BAD_REQUEST, "ARCHIVE_SOURCE_REVISION_REQUIRED", "项目没有当前源码版本"));
        TaskResponse task = taskService.create(new TaskCreateCommand(
                projectId,
                RvPortTaskTypes.ARCHIVE_PROJECT,
                Map.of("projectId", projectId.toString(), "sourceRevisionId", active.id().toString()),
                actorUserId,
                null,
                "项目归档任务已创建"
        ));
        ProjectArchiveView archive = archiveRepository.create(
                projectId,
                active.id(),
                task.id(),
                "项目归档 - " + label(active),
                actorUserId
        );
        return new ProjectArchiveCreateResponse(archive.id(), active.id(), task);
    }

    @Transactional(readOnly = true)
    public ProjectArchiveOverviewResponse overview(UUID projectId, UUID actorUserId, boolean superAdmin) {
        projectAccessService.requireProjectAccess(projectId, actorUserId, superAdmin);
        return new ProjectArchiveOverviewResponse(archiveRepository.latest(projectId).map(this::response).orElse(null));
    }

    @Transactional(readOnly = true)
    public DomainLatestResponse<ProjectArchiveResponse> latest(UUID projectId, UUID actorUserId, boolean superAdmin) {
        projectAccessService.requireProjectAccess(projectId, actorUserId, superAdmin);
        ProjectContextSnapshot context = projectContextService.snapshot(projectId);
        return archiveRepository.latest(projectId, context.sourceRevisionId())
                .map(archive -> DomainLatestResponse.current(
                        context,
                        DomainLatestExecutionResponse.from(archive.id(), taskRepository.findById(archive.taskId()).orElse(null)),
                        response(archive)))
                .orElseGet(() -> archiveRepository.latest(projectId)
                        .map(archive -> DomainLatestResponse.stale(
                                context,
                                DomainLatestExecutionResponse.from(archive.id(), taskRepository.findById(archive.taskId()).orElse(null)),
                                response(archive)))
                        .orElseGet(() -> DomainLatestResponse.empty(context)));
    }

    @Transactional(readOnly = true)
    public PageResponse<ProjectArchiveResponse> list(UUID projectId, ProjectArchiveListRequest request, UUID actorUserId, boolean superAdmin) {
        projectAccessService.requireProjectAccess(projectId, actorUserId, superAdmin);
        int page = request.normalizedPage();
        int pageSize = request.normalizedPageSize();
        try {
            long total = archiveRepository.count(projectId, request);
            List<ProjectArchiveResponse> items = archiveRepository.list(projectId, request).stream()
                    .map(this::responseWithoutItems)
                    .toList();
            return PageResponse.of(items, page, pageSize, total);
        } catch (IllegalArgumentException ex) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "ARCHIVE_QUERY_INVALID", "归档查询参数不正确");
        }
    }

    @Transactional(readOnly = true)
    public ProjectArchiveResponse get(UUID archiveId, UUID actorUserId, boolean superAdmin) {
        ProjectArchiveView archive = requireArchive(archiveId, actorUserId, superAdmin);
        return response(archive);
    }

    @Transactional(readOnly = true)
    public ProjectArchiveDownload download(UUID archiveId, UUID actorUserId, boolean superAdmin) {
        ProjectArchiveView archive = requireArchive(archiveId, actorUserId, superAdmin);
        if (archive.storedArtifactId() == null) {
            throw new ApiException(HttpStatus.NOT_FOUND, "ARCHIVE_ARTIFACT_NOT_FOUND", "归档包不存在");
        }
        StoredArtifactResource resource = storedArtifactService.download(archive.storedArtifactId());
        return new ProjectArchiveDownload(resource.resource(), safeArchiveFilename(archive), resource.artifact().contentType());
    }

    @Transactional(readOnly = true)
    public ProjectArchiveDownload downloadItem(UUID archiveId, UUID itemId, String format, UUID actorUserId, boolean superAdmin) {
        ProjectArchiveView archive = requireArchive(archiveId, actorUserId, superAdmin);
        ProjectArchiveItemView item = archiveRepository.findItem(archive.id(), itemId)
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "ARCHIVE_ITEM_NOT_FOUND", "归档项不存在"));
        ArchiveArtifactRef ref = item.artifactRefs().stream()
                .filter(candidate -> candidate.format() != null && candidate.format().equalsIgnoreCase(format))
                .findFirst()
                .orElse(null);
        if (ref == null && "JSON".equalsIgnoreCase(format)) {
            return metadataDownload(item);
        }
        if (ref == null) {
            throw new ApiException(HttpStatus.NOT_FOUND, "ARCHIVE_ITEM_FORMAT_NOT_FOUND", "归档项格式不存在");
        }
        if (ref.storedArtifactId() == null) {
            throw new ApiException(HttpStatus.NOT_FOUND, "ARCHIVE_ITEM_ARTIFACT_NOT_FOUND", "归档项制品不存在");
        }
        StoredArtifactResource resource = storedArtifactService.download(ref.storedArtifactId());
        return new ProjectArchiveDownload(resource.resource(), safeFilename(ref.filename(), item, ref.format()), resource.artifact().contentType());
    }

    private ProjectArchiveDownload metadataDownload(ProjectArchiveItemView item) {
        try {
            byte[] content = objectMapper.writerWithDefaultPrettyPrinter().writeValueAsBytes(item.metadata());
            return new ProjectArchiveDownload(
                    new ByteArrayResource(content),
                    safeFilename(null, item, "JSON"),
                    "application/json; charset=" + StandardCharsets.UTF_8.name()
            );
        } catch (IOException ex) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "ARCHIVE_ITEM_METADATA_INVALID", "归档项摘要无法序列化");
        }
    }

    @Transactional(readOnly = true)
    public ProjectArchiveView requireInternalByTaskId(UUID taskId) {
        return archiveRepository.findByTaskId(taskId)
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "ARCHIVE_NOT_FOUND", "归档记录不存在"));
    }

    @Transactional(readOnly = true)
    public List<ArchiveCandidateView> activeCandidates(UUID projectId, UUID sourceRevisionId) {
        return candidateService.listActive(projectId, sourceRevisionId);
    }

    public ProjectArchiveView markRunning(UUID archiveId) {
        return archiveRepository.markRunning(archiveId);
    }

    public ProjectArchiveItemView createItem(UUID archiveId, ArchiveCandidateView candidate) {
        return archiveRepository.createItem(archiveId, candidate);
    }

    public ProjectArchiveView markSucceeded(UUID archiveId, UUID storedArtifactId, long sizeBytes, String sha256, Map<String, ?> summary) {
        return archiveRepository.markSucceeded(archiveId, storedArtifactId, sizeBytes, sha256, summary);
    }

    public ProjectArchiveView markFailed(UUID archiveId, Map<String, ?> summary) {
        return archiveRepository.markFailed(archiveId, summary);
    }

    private ProjectArchiveView requireArchive(UUID archiveId, UUID actorUserId, boolean superAdmin) {
        ProjectArchiveView archive = archiveRepository.findById(archiveId)
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "ARCHIVE_NOT_FOUND", "归档记录不存在"));
        projectAccessService.requireProjectAccess(archive.projectId(), actorUserId, superAdmin);
        return archive;
    }

    private ProjectArchiveResponse response(ProjectArchiveView archive) {
        List<ProjectArchiveItemResponse> items = archiveRepository.listItems(archive.id()).stream()
                .map(ProjectArchiveItemResponse::from)
                .toList();
        return response(archive, items);
    }

    private ProjectArchiveResponse responseWithoutItems(ProjectArchiveView archive) {
        return response(archive, List.of());
    }

    private ProjectArchiveResponse response(ProjectArchiveView archive, List<ProjectArchiveItemResponse> items) {
        SourceRevisionResponse revision = archive.sourceRevisionId() == null
                ? null
                : sourceRepository.findById(archive.sourceRevisionId()).map(SourceRevisionResponse::from).orElse(null);
        return new ProjectArchiveResponse(
                archive.id(),
                archive.projectId(),
                archive.sourceRevisionId(),
                revision,
                archive.taskId(),
                archive.storedArtifactId(),
                archive.name(),
                archive.status(),
                archive.summary(),
                archive.sizeBytes(),
                archive.sha256(),
                items,
                archive.createdAt(),
                archive.updatedAt()
        );
    }

    private String label(SourceRevisionView revision) {
        if (revision.versionLabel() != null && !revision.versionLabel().isBlank()) {
            return revision.versionLabel();
        }
        return revision.id().toString();
    }

    private String safeArchiveFilename(ProjectArchiveView archive) {
        return "rvport-archive-" + archive.id() + ".zip";
    }

    private String safeFilename(String filename, ProjectArchiveItemView item, String format) {
        if (filename != null && !filename.isBlank() && !filename.contains("/") && !filename.contains("\\") && !filename.contains("..")) {
            return filename;
        }
        return item.nodeType().name().toLowerCase() + "-" + item.id() + "." + format.toLowerCase();
    }
}
