package cn.rvport.backend.source;

import cn.rvport.backend.audit.AuditLogService;
import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.config.RvPortProperties;
import cn.rvport.backend.credential.CredentialKind;
import cn.rvport.backend.credential.CredentialService;
import cn.rvport.backend.credential.CredentialView;
import cn.rvport.backend.project.ProjectRepository;
import cn.rvport.backend.project.ProjectSourceInputType;
import cn.rvport.backend.project.ProjectStage;
import cn.rvport.backend.project.ProjectView;
import cn.rvport.backend.project.ProjectAccessService;
import cn.rvport.backend.optimization.OptimizationCycleService;
import cn.rvport.backend.source.archive.SourceArchiveException;
import cn.rvport.backend.source.archive.SourceArchiveExtraction;
import cn.rvport.backend.source.archive.SourceArchiveExtractor;
import cn.rvport.backend.task.RvPortTaskTypes;
import cn.rvport.backend.task.TaskCreateCommand;
import cn.rvport.backend.task.TaskEventResource;
import cn.rvport.backend.task.TaskEventService;
import cn.rvport.backend.task.TaskResponse;
import cn.rvport.backend.task.TaskService;
import cn.rvport.backend.task.TaskStatus;
import jakarta.servlet.http.HttpServletRequest;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

@Service
public class SourceService {

    private final SourceRepository sourceRepository;
    private final ProjectRepository projectRepository;
    private final CredentialService credentialService;
    private final TaskService taskService;
    private final GitUrlValidator gitUrlValidator;
    private final RvPortProperties properties;
    private final AuditLogService auditLogService;
    private final ProjectAccessService projectAccessService;
    private final SourceArchiveExtractor archiveExtractor;
    private final OptimizationCycleService optimizationCycleService;
    private final TaskEventService taskEventService;

    public SourceService(
            SourceRepository sourceRepository,
            ProjectRepository projectRepository,
            CredentialService credentialService,
            TaskService taskService,
            GitUrlValidator gitUrlValidator,
            RvPortProperties properties,
            AuditLogService auditLogService,
            ProjectAccessService projectAccessService,
            SourceArchiveExtractor archiveExtractor,
            OptimizationCycleService optimizationCycleService,
            TaskEventService taskEventService
    ) {
        this.sourceRepository = sourceRepository;
        this.projectRepository = projectRepository;
        this.credentialService = credentialService;
        this.taskService = taskService;
        this.gitUrlValidator = gitUrlValidator;
        this.properties = properties;
        this.auditLogService = auditLogService;
        this.projectAccessService = projectAccessService;
        this.archiveExtractor = archiveExtractor;
        this.optimizationCycleService = optimizationCycleService;
        this.taskEventService = taskEventService;
    }

    @Transactional(readOnly = true)
    public PageResponse<SourceRevisionResponse> list(UUID projectId, SourceListRequest request, UUID actorUserId, boolean superAdmin) {
        projectAccessService.requireProjectAccess(projectId, actorUserId, superAdmin);
        int page = request.normalizedPage();
        int pageSize = request.normalizedPageSize();
        long total = sourceRepository.count(projectId, request.revisionType(), request.active());
        List<SourceRevisionResponse> items = sourceRepository.list(projectId, request.revisionType(), request.active(), page, pageSize)
                .stream()
                .map(SourceRevisionResponse::from)
                .toList();
        return PageResponse.of(items, page, pageSize, total);
    }

    @Transactional
    public SourceArchiveResponse uploadArchive(
            UUID projectId,
            MultipartFile file,
            String versionLabel,
            String versionNote,
            boolean activate,
            UUID actorUserId,
            boolean superAdmin,
            HttpServletRequest request
    ) {
        ProjectView project = projectAccessService.requireProjectAccess(projectId, actorUserId, superAdmin);
        requireSourceInputType(project, ProjectSourceInputType.ARCHIVE);
        if (file == null || file.isEmpty()) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "SOURCE_ARCHIVE_INVALID", "源码包不能为空");
        }
        UUID sourceRevisionId = UUID.randomUUID();
        String displayName = UploadFileNames.safeDisplayName(file.getOriginalFilename());
        Path target = archiveTarget(projectId, sourceRevisionId, displayName);
        SourceArchiveExtraction extraction;
        try {
            Files.createDirectories(target.getParent());
            file.transferTo(target);
            extraction = archiveExtractor.extract(target, displayName, sourceTarget(projectId, sourceRevisionId));
        } catch (SourceArchiveException ex) {
            deleteRecursively(target.getParent());
            throw new ApiException(HttpStatus.BAD_REQUEST, ex.code().name(), ex.getMessage());
        } catch (IOException ex) {
            deleteRecursively(target.getParent());
            throw new ApiException(HttpStatus.INTERNAL_SERVER_ERROR, "SOURCE_ARCHIVE_SAVE_FAILED", "源码包保存失败");
        }

        if (activate) {
            sourceRepository.clearActive(projectId);
        }
        SourceRevisionView revision = sourceRepository.createArchive(
                sourceRevisionId,
                projectId,
                versionLabel,
                displayName,
                target.toString(),
                extraction.workingCopyPath().toString(),
                versionNote,
                activate,
                actorUserId
        );
        SourceImportView sourceImport = sourceRepository.createImport(
                projectId,
                revision.id(),
                SourceRevisionType.ARCHIVE,
                TaskStatus.SUCCEEDED
        );
        projectRepository.lockSourceInputTypeIfEmpty(projectId, ProjectSourceInputType.ARCHIVE);
        projectRepository.updateStage(projectId, ProjectStage.SOURCE_IMPORTED);
        if (activate) {
            optimizationCycleService.createOrReuseActiveCycle(projectId, revision.id());
            publishActiveSourceChanged(projectId, revision.id(), "项目源码版本已更新");
        }
        auditLogService.record(projectId, actorUserId, "source.archive.upload", "source_revision", revision.id(),
                Map.of("filename", displayName, "activate", activate), request);
        return new SourceArchiveResponse(SourceRevisionResponse.from(revision), SourceImportResponse.from(sourceImport));
    }

    @Transactional
    public SourceRevisionResponse activate(UUID projectId, UUID sourceRevisionId, UUID actorUserId, boolean superAdmin, HttpServletRequest request) {
        projectAccessService.requireSourceRevisionAccess(projectId, sourceRevisionId, actorUserId, superAdmin);
        sourceRepository.clearActive(projectId);
        SourceRevisionView activated = sourceRepository.activate(projectId, sourceRevisionId);
        projectRepository.updateStage(projectId, ProjectStage.SOURCE_IMPORTED);
        optimizationCycleService.createOrReuseActiveCycle(projectId, sourceRevisionId);
        publishActiveSourceChanged(projectId, sourceRevisionId, "项目源码版本已激活");
        auditLogService.record(projectId, actorUserId, "source.activate", "source_revision", sourceRevisionId,
                Map.of("revisionType", activated.revisionType().name()), request);
        return SourceRevisionResponse.from(activated);
    }

    @Transactional
    public TaskResponse gitSync(UUID projectId, GitSyncRequest request, UUID actorUserId, boolean superAdmin, HttpServletRequest httpRequest) {
        ProjectView project = projectAccessService.requireProjectAccess(projectId, actorUserId, superAdmin);
        requireSourceInputType(project, ProjectSourceInputType.GIT);
        String gitUrl = gitUrlValidator.sanitize(request.gitUrl());
        UUID credentialId = resolveGitCredential(projectId, gitUrl, request, actorUserId);
        SourceImportView sourceImport = sourceRepository.createImport(projectId, null, SourceRevisionType.GIT, TaskStatus.PENDING);
        Map<String, Object> input = new LinkedHashMap<>();
        input.put("projectId", projectId);
        input.put("sourceImportId", sourceImport.id());
        input.put("gitUrl", gitUrl);
        input.put("gitBranch", blankToNull(request.gitBranch()));
        input.put("gitCommit", blankToNull(request.gitCommit()));
        input.put("credentialId", credentialId);
        input.put("versionLabel", blankToNull(request.versionLabel()));
        input.put("versionNote", blankToNull(request.versionNote()));
        input.put("activate", Boolean.TRUE.equals(request.activate()));
        TaskResponse task = taskService.create(new TaskCreateCommand(
                projectId,
                RvPortTaskTypes.SOURCE_GIT_SYNC,
                input,
                actorUserId,
                null,
                "Git 同步任务已创建"
        ));
        sourceRepository.attachTask(sourceImport.id(), task.id(), task.status());
        auditLogService.record(projectId, actorUserId, "source.git_sync", "source_import", sourceImport.id(),
                Map.of("taskId", task.id(), "gitUrl", gitUrl, "hasCredential", credentialId != null), httpRequest);
        return task;
    }

    public SourceRevisionResponse activeSource(UUID projectId) {
        return sourceRepository.findActive(projectId)
                .map(SourceRevisionResponse::from)
                .orElse(null);
    }

    public long count(UUID projectId) {
        return sourceRepository.count(projectId, null, null);
    }

    private UUID resolveGitCredential(UUID projectId, String gitUrl, GitSyncRequest request, UUID actorUserId) {
        if (request.credentialId() != null) {
            return credentialService.requireActive(request.credentialId(), projectId).id();
        }
        String token = blankToNull(request.token());
        String password = blankToNull(request.password());
        if (token == null && password == null) {
            return null;
        }
        CredentialKind kind = request.credentialKind();
        if (kind == null) {
            kind = token != null ? CredentialKind.GIT_TOKEN : CredentialKind.GIT_PASSWORD;
        }
        String secret = kind == CredentialKind.GIT_TOKEN ? token : password;
        CredentialView credential = credentialService.create(credentialService.gitSecret(
                projectId,
                actorUserId,
                kind,
                request.credentialName(),
                gitUrl,
                request.username(),
                secret
        ));
        return credential.id();
    }

    private void publishActiveSourceChanged(UUID projectId, UUID sourceRevisionId, String message) {
        taskEventService.appendProjectContextChanged(
                projectId,
                "context",
                TaskEventResource.of("source_revision", sourceRevisionId),
                List.of("activeSourceRevision"),
                message
        );
    }

    private Path archiveTarget(UUID projectId, UUID sourceRevisionId, String displayName) {
        String uploadDir = properties.runtime() == null ? "./runtime/uploads" : properties.runtime().uploadDir();
        return Path.of(uploadDir == null || uploadDir.isBlank() ? "./runtime/uploads" : uploadDir)
                .resolve(projectId.toString())
                .resolve(sourceRevisionId.toString())
                .resolve(displayName)
                .normalize();
    }

    private Path sourceTarget(UUID projectId, UUID sourceRevisionId) {
        String sourceDir = properties.runtime() == null ? "./runtime/sources" : properties.runtime().sourceDir();
        return Path.of(sourceDir == null || sourceDir.isBlank() ? "./runtime/sources" : sourceDir)
                .resolve(projectId.toString())
                .resolve(sourceRevisionId.toString())
                .normalize();
    }

    private void requireSourceInputType(ProjectView project, ProjectSourceInputType expected) {
        if (project.sourceInputType() == null || project.sourceInputType() == expected) {
            return;
        }
        throw new ApiException(HttpStatus.CONFLICT, "SOURCE_INPUT_TYPE_LOCKED", "项目源码来源已锁定为 " + project.sourceInputType());
    }

    private void deleteRecursively(Path path) {
        if (path == null || !Files.exists(path)) {
            return;
        }
        try (var stream = Files.walk(path)) {
            stream.sorted(Comparator.reverseOrder()).forEach(item -> {
                try {
                    Files.deleteIfExists(item);
                } catch (IOException ignored) {
                    // 清理失败不覆盖主要错误。
                }
            });
        } catch (IOException ignored) {
            // 同上。
        }
    }

    private String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }
}
