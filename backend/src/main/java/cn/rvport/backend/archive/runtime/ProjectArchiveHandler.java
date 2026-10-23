package cn.rvport.backend.archive.runtime;

import cn.rvport.backend.archive.ArchiveArtifactRef;
import cn.rvport.backend.archive.ArchiveCandidateView;
import cn.rvport.backend.archive.ProjectArchiveInput;
import cn.rvport.backend.archive.ProjectArchiveItemView;
import cn.rvport.backend.archive.ProjectArchiveService;
import cn.rvport.backend.archive.ProjectArchiveView;
import cn.rvport.backend.artifact.StoredArtifactCreateCommand;
import cn.rvport.backend.artifact.StoredArtifactOwnerType;
import cn.rvport.backend.artifact.StoredArtifactResource;
import cn.rvport.backend.artifact.StoredArtifactService;
import cn.rvport.backend.artifact.StoredArtifactView;
import cn.rvport.backend.task.RvPortTaskTypes;
import cn.rvport.backend.task.TaskErrorCode;
import cn.rvport.backend.task.TaskExecutionException;
import cn.rvport.backend.task.TaskLogType;
import cn.rvport.backend.worker.TaskExecutionContext;
import cn.rvport.backend.worker.TaskAttemptLostException;
import cn.rvport.backend.worker.TaskHandler;
import cn.rvport.backend.worker.TaskHandlerResult;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;
import org.springframework.stereotype.Component;

@Component
public class ProjectArchiveHandler implements TaskHandler {

    private final ProjectArchiveService archiveService;
    private final StoredArtifactService storedArtifactService;
    private final ObjectMapper objectMapper;

    public ProjectArchiveHandler(
            ProjectArchiveService archiveService,
            StoredArtifactService storedArtifactService,
            ObjectMapper objectMapper
    ) {
        this.archiveService = archiveService;
        this.storedArtifactService = storedArtifactService;
        this.objectMapper = objectMapper;
    }

    @Override
    public String taskType() {
        return RvPortTaskTypes.ARCHIVE_PROJECT;
    }

    @Override
    public TaskHandlerResult handle(TaskExecutionContext context) {
        ProjectArchiveView archive = archiveService.requireInternalByTaskId(context.task().id());
        ProjectArchiveInput input = context.input(ProjectArchiveInput.class);
        if (!archive.projectId().equals(input.projectId()) || !archive.sourceRevisionId().equals(input.sourceRevisionId())) {
            throw new TaskExecutionException(TaskErrorCode.PROJECT_MISMATCH, "归档任务输入和归档记录不匹配", null);
        }
        try {
            context.publish(() -> { archiveService.markRunning(archive.id()); return null; });
            context.progress(10, "读取待归档候选");
            List<ArchiveCandidateView> candidates = archiveService.activeCandidates(archive.projectId(), archive.sourceRevisionId());
            if (candidates.isEmpty()) {
                context.publish(() -> {
                    archiveService.markFailed(archive.id(), Map.of("errorCode", "ARCHIVE_NO_CANDIDATES", "message", "当前源码版本没有可归档内容"));
                    return null;
                });
                throw new TaskExecutionException(TaskErrorCode.INPUT_INVALID, "当前源码版本没有可归档内容", null);
            }

            context.progress(25, "固化归档项");
            List<ProjectArchiveItemView> items = new ArrayList<>();
            for (ArchiveCandidateView candidate : candidates) {
                items.add(context.publish(() -> archiveService.createItem(archive.id(), candidate)));
            }

            context.progress(55, "生成归档包");
            byte[] zip = createZip(archive, items);
            context.log(TaskLogType.TOOL, "归档包已生成，归档项数量：" + items.size());

            context.progress(80, "保存归档包");
            Map<String, Object> summary = summary(archive, items);
            StoredArtifactView artifact = storedArtifactService.store(new StoredArtifactCreateCommand(
                    archive.projectId(),
                    context.task().id(),
                    StoredArtifactOwnerType.ARCHIVE,
                    archive.id(),
                    "PROJECT_ARCHIVE_ZIP",
                    "application/zip",
                    zip,
                    summary,
                    "zip"
            ), context);
            context.publish(() -> {
                archiveService.markSucceeded(archive.id(), artifact.id(), artifact.sizeBytes(), artifact.sha256(), summary);
                return null;
            });
            context.progress(95, "归档完成");
            return TaskHandlerResult.success("项目归档完成");
        } catch (TaskAttemptLostException ex) {
            throw ex;
        } catch (TaskExecutionException ex) {
            throw ex;
        } catch (RuntimeException ex) {
            context.publish(() -> {
                archiveService.markFailed(archive.id(), Map.of("errorCode", TaskErrorCode.HANDLER_FAILED, "message", safeMessage(ex)));
                return null;
            });
            throw new TaskExecutionException(TaskErrorCode.HANDLER_FAILED, "项目归档失败", ex);
        }
    }

    private byte[] createZip(ProjectArchiveView archive, List<ProjectArchiveItemView> items) {
        try {
            ByteArrayOutputStream bytes = new ByteArrayOutputStream();
            try (ZipOutputStream zip = new ZipOutputStream(bytes, StandardCharsets.UTF_8)) {
                putJson(zip, "manifest.json", manifest(archive, items));
                putJson(zip, "summary.json", summary(archive, items));
                for (ProjectArchiveItemView item : items) {
                    putJson(zip, summaryEntryName(item), item.metadata());
                    for (ArchiveArtifactRef ref : item.artifactRefs()) {
                        if (ref.storedArtifactId() == null) {
                            continue;
                        }
                        StoredArtifactResource resource = storedArtifactService.download(ref.storedArtifactId());
                        putBytes(zip, entryName(item, ref), resource.resource().getContentAsByteArray());
                    }
                }
            }
            return bytes.toByteArray();
        } catch (IOException ex) {
            throw new TaskExecutionException(TaskErrorCode.HANDLER_FAILED, "归档包生成失败", ex);
        }
    }

    private Map<String, Object> manifest(ProjectArchiveView archive, List<ProjectArchiveItemView> items) {
        return Map.of(
                "schemaVersion", "rvport.archive/v1",
                "archiveId", archive.id().toString(),
                "projectId", archive.projectId().toString(),
                "sourceRevisionId", archive.sourceRevisionId().toString(),
                "itemCount", items.size(),
                "items", items.stream().map(item -> {
                    Map<String, Object> value = new LinkedHashMap<>();
                    value.put("id", item.id().toString());
                    value.put("nodeType", item.nodeType().name());
                    value.put("candidateType", item.candidateType().name());
                    value.put("candidateKey", item.candidateKey());
                    value.put("title", item.title());
                    value.put("formats", item.artifactRefs().stream().map(ArchiveArtifactRef::format).toList());
                    return value;
                }).toList()
        );
    }

    private Map<String, Object> summary(ProjectArchiveView archive, List<ProjectArchiveItemView> items) {
        Map<String, Long> byNode = items.stream()
                .collect(java.util.stream.Collectors.groupingBy(item -> item.nodeType().name(), LinkedHashMap::new, java.util.stream.Collectors.counting()));
        return Map.of(
                "schemaVersion", "rvport.archive-summary/v1",
                "sourceRevisionId", archive.sourceRevisionId().toString(),
                "itemCount", items.size(),
                "byNodeType", byNode,
                "formats", items.stream().flatMap(item -> item.artifactRefs().stream()).map(ArchiveArtifactRef::format).distinct().toList()
        );
    }

    private void putJson(ZipOutputStream zip, String name, Object value) throws IOException {
        putBytes(zip, name, objectMapper.writerWithDefaultPrettyPrinter().writeValueAsBytes(value));
    }

    private void putBytes(ZipOutputStream zip, String name, byte[] content) throws IOException {
        ZipEntry entry = new ZipEntry(name);
        zip.putNextEntry(entry);
        zip.write(content);
        zip.closeEntry();
    }

    private String entryName(ProjectArchiveItemView item, ArchiveArtifactRef ref) {
        String filename = ref.filename();
        if (filename == null || filename.isBlank() || filename.contains("/") || filename.contains("\\") || filename.contains("..")) {
            filename = item.nodeType().name().toLowerCase() + "-" + item.id() + "." + ref.format().toLowerCase();
        }
        return "items/%s/%s/%s".formatted(item.nodeType().name().toLowerCase(), item.candidateType().name().toLowerCase(), filename);
    }

    private String summaryEntryName(ProjectArchiveItemView item) {
        return "items/%s/%s/summary-%s.json".formatted(
                item.nodeType().name().toLowerCase(),
                item.candidateType().name().toLowerCase(),
                item.id()
        );
    }

    private String safeMessage(RuntimeException ex) {
        String message = ex.getMessage();
        return message == null || message.isBlank() ? "项目归档失败" : message;
    }
}
