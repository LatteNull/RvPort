package cn.rvport.backend.source.runtime;

import cn.rvport.backend.config.RvPortProperties;
import cn.rvport.backend.credential.CredentialService;
import cn.rvport.backend.project.ProjectRepository;
import cn.rvport.backend.project.ProjectSourceInputType;
import cn.rvport.backend.project.ProjectStage;
import cn.rvport.backend.project.ProjectView;
import cn.rvport.backend.optimization.OptimizationCycleService;
import cn.rvport.backend.source.SourceRepository;
import cn.rvport.backend.source.SourceRevisionView;
import cn.rvport.backend.task.TaskErrorCode;
import cn.rvport.backend.task.TaskEventResource;
import cn.rvport.backend.task.TaskEventService;
import cn.rvport.backend.task.TaskExecutionException;
import cn.rvport.backend.task.TaskLogType;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.task.ToolRunRepository;
import cn.rvport.backend.worker.TaskExecutionContext;
import cn.rvport.backend.worker.TaskAttemptLostException;
import java.io.IOException;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.time.Duration;
import java.time.OffsetDateTime;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Service;

@Service
public class SourceFetchRuntimeService {

    private static final String TOOL_NAME = "rvport-git-sync";
    private static final String TOOL_VERSION = "1";

    private final SourceRepository sourceRepository;
    private final ProjectRepository projectRepository;
    private final CredentialService credentialService;
    private final GitClientAdapter gitClientAdapter;
    private final ToolRunRepository toolRunRepository;
    private final RvPortProperties properties;
    private final OptimizationCycleService optimizationCycleService;
    private final TaskEventService taskEventService;

    public SourceFetchRuntimeService(
            SourceRepository sourceRepository,
            ProjectRepository projectRepository,
            CredentialService credentialService,
            GitClientAdapter gitClientAdapter,
            ToolRunRepository toolRunRepository,
            RvPortProperties properties,
            OptimizationCycleService optimizationCycleService,
            TaskEventService taskEventService
    ) {
        this.sourceRepository = sourceRepository;
        this.projectRepository = projectRepository;
        this.credentialService = credentialService;
        this.gitClientAdapter = gitClientAdapter;
        this.toolRunRepository = toolRunRepository;
        this.properties = properties;
        this.optimizationCycleService = optimizationCycleService;
        this.taskEventService = taskEventService;
    }

    public SourceRevisionView sync(SourceGitSyncInput input, TaskExecutionContext context) {
        validate(input, context);
        context.throwIfCancellationRequested();
        UUID toolRunId = createToolRun(context);
        UUID revisionId = UUID.randomUUID();
        Path projectRoot = sourceRoot().resolve(input.projectId().toString()).normalize();
        Path tempDir = projectRoot.resolve(".tmp-" + revisionId).normalize();
        Path finalDir = projectRoot.resolve(revisionId.toString()).normalize();
        CredentialService.GitRuntimeCredential credential = null;
        try {
            context.progress(10, "开始 Git 源码同步");
            context.publish(() -> { requireGitSourceInput(input); return null; });
            context.throwIfCancellationRequested();
            deleteRecursively(tempDir);
            Files.createDirectories(projectRoot);
            credential = input.credentialId() == null ? null : credentialService.gitRuntimeCredential(input.credentialId(), input.projectId());
            GitSyncResult result = gitClientAdapter.sync(new GitSyncCommand(
                    input.gitUrl(),
                    blankToNull(input.gitBranch()),
                    blankToNull(input.gitCommit()),
                    tempDir,
                    credential,
                    Duration.ofMinutes(5),
                    process -> context.registerLocalProcess(process, Duration.ofSeconds(5))
            ));
            context.throwIfCancellationRequested();
            writeLogs(context, result);
            if (result.exitCode() != 0) {
                fail(toolRunId, input.sourceImportId(), result.exitCode(), "Git 同步失败", result, credential, context);
            }
            moveWorktree(tempDir, finalDir);
            context.throwIfCancellationRequested();
            SourceRevisionView revision = context.publish(() -> {
            if (input.activate()) {
                sourceRepository.clearActive(input.projectId());
            }
            SourceRevisionView created = sourceRepository.createGit(
                    revisionId,
                    input.projectId(),
                    input.versionLabel(),
                    input.gitUrl(),
                    input.gitBranch(),
                    result.actualCommit(),
                    finalDir.toString(),
                    input.versionNote(),
                    input.activate(),
                    context.task().createdBy()
            );
            projectRepository.lockSourceInputTypeIfEmpty(input.projectId(), ProjectSourceInputType.GIT);
            sourceRepository.completeImport(input.sourceImportId(), created.id());
            projectRepository.updateStage(input.projectId(), ProjectStage.SOURCE_IMPORTED);
            if (input.activate()) {
                optimizationCycleService.createOrReuseActiveCycle(input.projectId(), created.id());
                taskEventService.appendProjectContextChanged(
                        input.projectId(),
                        "context",
                        TaskEventResource.of("source_revision", created.id()),
                        java.util.List.of("activeSourceRevision"),
                        "项目源码版本已更新"
                );
            }
            toolRunRepository.finish(toolRunId, TaskStatus.SUCCEEDED, result.exitCode(), successSummary(input, created, result));
            return created;
            });
            context.progress(90, "Git 源码同步完成");
            return revision;
        } catch (TaskAttemptLostException ex) {
            deleteRecursively(tempDir);
            // A published revision may already refer to finalDir; never delete it on late failure.
            throw ex;
        } catch (TaskExecutionException ex) {
            deleteRecursively(tempDir);
            throw ex;
        } catch (Exception ex) {
            deleteRecursively(tempDir);
            context.publish(() -> {
                sourceRepository.failImport(input.sourceImportId(), "Git 同步失败");
                toolRunRepository.finish(toolRunId, TaskStatus.FAILED, null, Map.of("error", "Git 同步失败"));
                return null;
            });
            throw new TaskExecutionException(TaskErrorCode.HANDLER_FAILED, "Git 同步失败", ex);
        }
    }

    private void validate(SourceGitSyncInput input, TaskExecutionContext context) {
        if (input == null || input.projectId() == null || input.sourceImportId() == null || input.gitUrl() == null || input.gitUrl().isBlank()) {
            throw new TaskExecutionException(TaskErrorCode.INPUT_INVALID, "Git 同步任务输入非法", null);
        }
        if (!input.projectId().equals(context.task().projectId())) {
            throw new TaskExecutionException(TaskErrorCode.INPUT_INVALID, "Git 同步任务项目不匹配", null);
        }
    }

    private void requireGitSourceInput(SourceGitSyncInput input) {
        ProjectView project = projectRepository.findById(input.projectId())
                .orElseThrow(() -> new TaskExecutionException(TaskErrorCode.INPUT_INVALID, "项目不存在", null));
        if (project.sourceInputType() == ProjectSourceInputType.ARCHIVE) {
            sourceRepository.failImport(input.sourceImportId(), "项目源码来源已锁定为 ARCHIVE");
            throw new TaskExecutionException(TaskErrorCode.INPUT_INVALID, "项目源码来源已锁定为 ARCHIVE", null);
        }
    }

    private UUID createToolRun(TaskExecutionContext context) {
        return context.publish(() -> toolRunRepository.create(
                context.task().projectId(),
                context.task().id(),
                TOOL_NAME,
                TOOL_VERSION,
                "Git 源码同步",
                TaskStatus.RUNNING,
                OffsetDateTime.now()
        ));
    }

    private void writeLogs(TaskExecutionContext context, GitSyncResult result) {
        if (result.stdout() != null && !result.stdout().isBlank()) {
            context.log(TaskLogType.STDOUT, result.stdout());
        }
        if (result.stderr() != null && !result.stderr().isBlank()) {
            context.log(TaskLogType.STDERR, result.stderr());
        }
    }

    private void fail(
            UUID toolRunId,
            UUID sourceImportId,
            int exitCode,
            String message,
            GitSyncResult result,
            CredentialService.GitRuntimeCredential credential,
            TaskExecutionContext context
    ) {
        context.publish(() -> {
        sourceRepository.failImport(sourceImportId, message);
        toolRunRepository.finish(toolRunId, TaskStatus.FAILED, exitCode, Map.of(
                "error", message,
                "durationMs", result.duration().toMillis(),
                "hasCredential", credential != null
        ));
        return null;
        });
        throw new TaskExecutionException(TaskErrorCode.HANDLER_FAILED, message, null);
    }

    private Map<String, Object> successSummary(SourceGitSyncInput input, SourceRevisionView revision, GitSyncResult result) {
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("gitUrl", input.gitUrl());
        summary.put("gitBranch", blankToNull(input.gitBranch()));
        summary.put("gitCommit", revision.gitCommit());
        summary.put("sourceRevisionId", revision.id());
        summary.put("activated", revision.active());
        summary.put("durationMs", result.duration().toMillis());
        return summary;
    }

    private void moveWorktree(Path tempDir, Path finalDir) throws IOException {
        Files.createDirectories(finalDir.getParent());
        try {
            Files.move(tempDir, finalDir, StandardCopyOption.ATOMIC_MOVE);
        } catch (AtomicMoveNotSupportedException ex) {
            Files.move(tempDir, finalDir);
        }
    }

    private Path sourceRoot() {
        String value = properties.runtime() == null ? null : properties.runtime().sourceDir();
        return Path.of(value == null || value.isBlank() ? "./runtime/sources" : value)
                .toAbsolutePath()
                .normalize();
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
                    // 清理失败不覆盖主要执行结果，后续同名临时目录会再次尝试清理。
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
