package cn.rvport.backend.report.runtime;

import cn.rvport.backend.artifact.StoredArtifactCreateCommand;
import cn.rvport.backend.artifact.StoredArtifactOwnerType;
import cn.rvport.backend.artifact.StoredArtifactService;
import cn.rvport.backend.artifact.StoredArtifactView;
import cn.rvport.backend.common.path.ServerPathException;
import cn.rvport.backend.common.path.ServerPathGuard;
import cn.rvport.backend.report.ReportFileContextView;
import cn.rvport.backend.report.ReportOrganizationRepository;
import cn.rvport.backend.report.ReportRepository;
import cn.rvport.backend.report.ReportView;
import cn.rvport.backend.source.SourceRevisionView;
import cn.rvport.backend.worker.TaskExecutionContext;
import cn.rvport.backend.worker.TaskAttemptLostException;
import java.nio.ByteBuffer;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Service;

@Service
public class ReportFileContextSnapshotter {

    static final long MAX_SOURCE_FILE_BYTES = 10L * 1024 * 1024;

    private final StoredArtifactService storedArtifactService;
    private final ReportOrganizationRepository organizationRepository;

    public ReportFileContextSnapshotter(
            StoredArtifactService storedArtifactService,
            ReportOrganizationRepository organizationRepository
    ) {
        this.storedArtifactService = storedArtifactService;
        this.organizationRepository = organizationRepository;
    }

    public Map<String, String> capture(
            ReportView report,
            SourceRevisionView revision,
            List<ReportRepository.ReportInputSnapshot> snapshots,
            TaskExecutionContext context
    ) {
        Map<String, String> hashes = new LinkedHashMap<>();
        Map<String, ReportRepository.ReportInputSnapshot> files = new LinkedHashMap<>();
        for (ReportRepository.ReportInputSnapshot snapshot : snapshots) {
            if (snapshot.projection() != null && snapshot.projection().relativePath() != null
                    && snapshot.projection().fileKey() != null) {
                files.putIfAbsent(snapshot.projection().fileKey(), snapshot);
            }
        }
        for (ReportRepository.ReportInputSnapshot snapshot : files.values()) {
            captureFile(report, revision, snapshot, hashes, context);
        }
        return Map.copyOf(hashes);
    }

    private void captureFile(
            ReportView report,
            SourceRevisionView revision,
            ReportRepository.ReportInputSnapshot snapshot,
            Map<String, String> hashes,
            TaskExecutionContext context
    ) {
        String fileKey = snapshot.projection().fileKey();
        String relativePath = snapshot.projection().relativePath();
        try {
            if (revision == null || revision.workingCopyPath() == null || revision.workingCopyPath().isBlank()) {
                unavailable(report, revision, fileKey, relativePath, "SOURCE_REVISION_UNAVAILABLE", context);
                return;
            }
            Path root = Path.of(revision.workingCopyPath()).toAbsolutePath().normalize();
            Path file = ServerPathGuard.resolveExistingRelativeFileUnderRoot(root, relativePath);
            long size = Files.size(file);
            if (size > MAX_SOURCE_FILE_BYTES) {
                unavailable(report, revision, fileKey, relativePath, "FILE_TOO_LARGE", context);
                return;
            }
            byte[] bytes = Files.readAllBytes(file);
            if (containsNul(bytes)) {
                unavailable(report, revision, fileKey, relativePath, "BINARY_FILE", context);
                return;
            }
            String content = decodeUtf8(bytes);
            String hash = sha256(bytes);
            int totalLines = content.isEmpty() ? 0 : content.split("\\R", -1).length;
            StoredArtifactView artifact = storedArtifactService.store(new StoredArtifactCreateCommand(
                    report.projectId(), report.taskId(), StoredArtifactOwnerType.MIGRATION_REPORT, report.id(),
                    "SOURCE_CONTEXT_" + fileKey, "text/plain; charset=utf-8", bytes,
                    Map.of("fileKey", fileKey, "relativePath", relativePath, "contentHash", hash, "totalLines", totalLines),
                    "txt"
            ), context);
            context.publish(() -> {
            organizationRepository.upsertFileContext(new ReportFileContextView(
                    UUID.randomUUID(), report.id(), revision.id(), fileKey, relativePath, hash, totalLines,
                    artifact.id(), true, null, null
            ));
            return null;
            });
            hashes.put(fileKey, hash);
        } catch (TaskAttemptLostException ex) {
            throw ex;
        } catch (ServerPathException ex) {
            unavailable(report, revision, fileKey, relativePath, reason(ex), context);
        } catch (java.nio.charset.CharacterCodingException ex) {
            unavailable(report, revision, fileKey, relativePath, "INVALID_UTF8", context);
        } catch (Exception ex) {
            unavailable(report, revision, fileKey, relativePath, "CONTEXT_SNAPSHOT_FAILED", context);
        }
    }

    private void unavailable(ReportView report, SourceRevisionView revision, String fileKey, String relativePath, String reason, TaskExecutionContext context) {
        UUID sourceRevisionId = revision == null ? report.sourceRevisionId() : revision.id();
        context.publish(() -> {
        organizationRepository.upsertFileContext(new ReportFileContextView(
                UUID.randomUUID(), report.id(), sourceRevisionId, fileKey, relativePath, null, null,
                null, false, reason, null
        ));
        return null;
        });
    }

    private String reason(ServerPathException ex) {
        String message = ex.getMessage();
        if (message != null && (message.contains("outside") || message.contains("traversal") || message.contains("Absolute"))) {
            return "PATH_UNSAFE";
        }
        return "SOURCE_FILE_MISSING";
    }

    private String decodeUtf8(byte[] bytes) throws java.nio.charset.CharacterCodingException {
        return StandardCharsets.UTF_8.newDecoder()
                .onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT)
                .decode(ByteBuffer.wrap(bytes))
                .toString();
    }

    private boolean containsNul(byte[] bytes) {
        for (byte value : bytes) {
            if (value == 0) {
                return true;
            }
        }
        return false;
    }

    private String sha256(byte[] bytes) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }
}
