package cn.rvport.backend.artifact;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.worker.TaskExecutionContext;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class StoredArtifactService {

    private final ObjectStorageService objectStorageService;
    private final StoredArtifactRepository repository;
    private final ObjectMapper objectMapper;

    public StoredArtifactService(
            ObjectStorageService objectStorageService,
            StoredArtifactRepository repository,
            ObjectMapper objectMapper
    ) {
        this.objectStorageService = objectStorageService;
        this.repository = repository;
        this.objectMapper = objectMapper;
    }

    /** Upload outside the attempt transaction; only metadata publication holds the task lock. */
    public StoredArtifactView store(StoredArtifactCreateCommand command, TaskExecutionContext context) {
        validate(command);
        UUID artifactId = UUID.randomUUID();
        String hash = sha256(command.content());
        ObjectStoragePutResult put = objectStorageService.put(objectKey(command, artifactId), command.contentType(), command.content());
        return registerUploaded(command, context, artifactId, hash, put);
    }

    private StoredArtifactView registerUploaded(StoredArtifactCreateCommand command, TaskExecutionContext context,
            UUID artifactId, String hash, ObjectStoragePutResult put) {
        java.util.concurrent.atomic.AtomicBoolean completionRegistered = new java.util.concurrent.atomic.AtomicBoolean();
        try {
            return context.publish(() -> {
                StoredArtifactView previous = repository.findByOwner(command.ownerType(), command.ownerId(), command.artifactType()).orElse(null);
                StoredArtifactView created = repository.upsert(artifactId, command.projectId(), command.taskId(),
                        command.ownerType(), command.ownerId(), command.artifactType(), put.bucket(), put.objectKey(),
                        put.contentType(), put.sizeBytes(), hash, command.summary());
                if (org.springframework.transaction.support.TransactionSynchronizationManager.isSynchronizationActive()) {
                    org.springframework.transaction.support.TransactionSynchronizationManager.registerSynchronization(
                            new org.springframework.transaction.support.TransactionSynchronization() {
                                @Override
                                public void afterCompletion(int status) {
                                    if (status == STATUS_COMMITTED) {
                                        cleanupPrevious(previous, created);
                                    } else if (status == STATUS_ROLLED_BACK) {
                                        cleanupUploaded(put);
                                    }
                                }
                            });
                    completionRegistered.set(true);
                } else {
                    cleanupPrevious(previous, created);
                }
                return created;
            });
        } catch (RuntimeException ex) {
            if (!completionRegistered.get()) cleanupUploaded(put);
            throw ex;
        }
    }

    private void cleanupPrevious(StoredArtifactView previous, StoredArtifactView created) {
        if (previous != null && !previous.objectKey().equals(created.objectKey())) {
            cleanupUploaded(new ObjectStoragePutResult(previous.bucket(), previous.objectKey(), previous.contentType(), previous.sizeBytes()));
        }
    }

    private void cleanupUploaded(ObjectStoragePutResult put) {
        try {
            objectStorageService.delete(put.bucket(), put.objectKey());
        } catch (RuntimeException ex) {
            // Cleanup must not invalidate committed metadata or replace the original publication error.
            org.slf4j.LoggerFactory.getLogger(StoredArtifactService.class)
                    .warn("Artifact object cleanup deferred exceptionClass={}", ex.getClass().getSimpleName());
        }
    }

    public StoredArtifactView storeJson(UUID projectId, UUID taskId, StoredArtifactOwnerType ownerType,
            UUID ownerId, String artifactType, Object content, Map<String, ?> summary, TaskExecutionContext context) {
        try {
            return store(new StoredArtifactCreateCommand(projectId, taskId, ownerType, ownerId, artifactType,
                    "application/json", objectMapper.writeValueAsBytes(content), summary, "json"), context);
        } catch (IOException ex) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "ARTIFACT_CONTENT_INVALID", "制品内容无法序列化");
        }
    }

    public StoredArtifactView storeFile(UUID projectId, UUID taskId, StoredArtifactOwnerType ownerType,
            UUID ownerId, String artifactType, Path file, String contentType, Map<String, ?> summary,
            String extension, TaskExecutionContext context) throws IOException {
        return storeLargeFile(projectId, taskId, ownerType, ownerId, artifactType, file, contentType, summary, extension, context);
    }

    public StoredArtifactView storeLargeFile(UUID projectId, UUID taskId, StoredArtifactOwnerType ownerType,
            UUID ownerId, String artifactType, Path file, String contentType, Map<String, ?> summary,
            String extension, TaskExecutionContext context) throws IOException {
        StoredArtifactCreateCommand command = new StoredArtifactCreateCommand(projectId, taskId, ownerType,
                ownerId, artifactType, contentType, new byte[0], summary, extension);
        validate(command);
        if (file == null) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "ARTIFACT_INPUT_INVALID", "制品输入不完整");
        }
        UUID artifactId = UUID.randomUUID();
        String hash = sha256(file);
        ObjectStoragePutResult put = objectStorageService.putFile(objectKey(command, artifactId), contentType, file);
        return registerUploaded(command, context, artifactId, hash, put);
    }

    @Transactional
    public StoredArtifactView store(StoredArtifactCreateCommand command) {
        validate(command);
        UUID artifactId = UUID.randomUUID();
        StoredArtifactView previous = repository.findByOwner(command.ownerType(), command.ownerId(), command.artifactType()).orElse(null);
        String objectKey = objectKey(command, artifactId);
        ObjectStoragePutResult put = objectStorageService.put(objectKey, command.contentType(), command.content());
        try {
            StoredArtifactView created = repository.upsert(
                    artifactId,
                    command.projectId(),
                    command.taskId(),
                    command.ownerType(),
                    command.ownerId(),
                    command.artifactType(),
                    put.bucket(),
                    put.objectKey(),
                    put.contentType(),
                    put.sizeBytes(),
                    sha256(command.content()),
                    command.summary()
            );
            deletePrevious(previous, created);
            return created;
        } catch (RuntimeException ex) {
            objectStorageService.delete(put.bucket(), put.objectKey());
            throw ex;
        }
    }

    public StoredArtifactView storeFile(
            UUID projectId,
            UUID taskId,
            StoredArtifactOwnerType ownerType,
            UUID ownerId,
            String artifactType,
            Path file,
            String contentType,
            Map<String, ?> summary,
            String extension
    ) throws IOException {
        return store(new StoredArtifactCreateCommand(
                projectId,
                taskId,
                ownerType,
                ownerId,
                artifactType,
                contentType,
                Files.readAllBytes(file),
                summary,
                extension
        ));
    }

    @Transactional
    public StoredArtifactView storeLargeFile(
            UUID projectId,
            UUID taskId,
            StoredArtifactOwnerType ownerType,
            UUID ownerId,
            String artifactType,
            Path file,
            String contentType,
            Map<String, ?> summary,
            String extension
    ) throws IOException {
        if (projectId == null || ownerType == null || ownerId == null || artifactType == null
                || artifactType.isBlank() || contentType == null || contentType.isBlank() || file == null) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "ARTIFACT_INPUT_INVALID", "制品输入不完整");
        }
        UUID artifactId = UUID.randomUUID();
        StoredArtifactView previous = repository.findByOwner(ownerType, ownerId, artifactType).orElse(null);
        String objectKey = objectKey(new StoredArtifactCreateCommand(projectId, taskId, ownerType, ownerId,
                artifactType, contentType, new byte[0], summary, extension), artifactId);
        ObjectStoragePutResult put = objectStorageService.putFile(objectKey, contentType, file);
        try {
            StoredArtifactView created = repository.upsert(
                    artifactId, projectId, taskId, ownerType, ownerId, artifactType,
                    put.bucket(), put.objectKey(), put.contentType(), put.sizeBytes(), sha256(file), summary
            );
            deletePrevious(previous, created);
            return created;
        } catch (RuntimeException ex) {
            objectStorageService.delete(put.bucket(), put.objectKey());
            throw ex;
        }
    }

    public StoredArtifactView storeJson(
            UUID projectId,
            UUID taskId,
            StoredArtifactOwnerType ownerType,
            UUID ownerId,
            String artifactType,
            Object content,
            Map<String, ?> summary
    ) {
        try {
            return store(new StoredArtifactCreateCommand(
                    projectId,
                    taskId,
                    ownerType,
                    ownerId,
                    artifactType,
                    "application/json",
                    objectMapper.writeValueAsBytes(content),
                    summary,
                    "json"
            ));
        } catch (IOException ex) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "ARTIFACT_CONTENT_INVALID", "制品内容无法序列化");
        }
    }

    @Transactional(readOnly = true)
    public StoredArtifactResource download(UUID artifactId) {
        StoredArtifactView artifact = repository.findById(artifactId)
                .orElseThrow(() -> notFound("ARTIFACT_NOT_FOUND", "制品不存在"));
        try {
            ObjectStorageObject object = objectStorageService.get(artifact.bucket(), artifact.objectKey());
            return new StoredArtifactResource(artifact, new ByteArrayResource(object.content()));
        } catch (ObjectStorageException ex) {
            throw notFound("ARTIFACT_OBJECT_NOT_FOUND", "制品文件不存在");
        }
    }

    public void delete(UUID artifactId) {
        repository.findById(artifactId).ifPresent(artifact -> {
            objectStorageService.delete(artifact.bucket(), artifact.objectKey());
            repository.delete(artifact.id());
        });
    }

    public void delete(StoredArtifactView expected, TaskExecutionContext context) {
        context.publish(() -> {
            repository.findById(expected.id()).filter(value -> value.objectKey().equals(expected.objectKey()))
                    .ifPresent(value -> {
                        repository.delete(value.id());
                        ObjectStoragePutResult object = new ObjectStoragePutResult(value.bucket(), value.objectKey(), value.contentType(), value.sizeBytes());
                        if (org.springframework.transaction.support.TransactionSynchronizationManager.isSynchronizationActive()) {
                            org.springframework.transaction.support.TransactionSynchronizationManager.registerSynchronization(
                                    new org.springframework.transaction.support.TransactionSynchronization() {
                                        @Override public void afterCommit() { cleanupUploaded(object); }
                                    });
                        } else {
                            cleanupUploaded(object);
                        }
                    });
            return null;
        });
    }

    private void validate(StoredArtifactCreateCommand command) {
        if (command.projectId() == null || command.ownerType() == null || command.ownerId() == null || command.artifactType() == null
                || command.artifactType().isBlank() || command.contentType() == null || command.contentType().isBlank()
                || command.content() == null) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "ARTIFACT_INPUT_INVALID", "制品输入不完整");
        }
    }

    private String objectKey(StoredArtifactCreateCommand command, UUID artifactId) {
        String extension = safeToken(command.extension() == null || command.extension().isBlank() ? "bin" : command.extension());
        return "projects/%s/%s/%s/%s-%s.%s".formatted(
                command.projectId(),
                command.ownerType().name().toLowerCase(),
                command.ownerId(),
                safeToken(command.artifactType()).toLowerCase(),
                artifactId,
                extension
        );
    }

    private String safeToken(String value) {
        String normalized = value.replaceAll("[^A-Za-z0-9_.-]", "_");
        while (normalized.contains("..")) {
            normalized = normalized.replace("..", ".");
        }
        normalized = normalized.replaceAll("^\\.+", "").replaceAll("\\.+$", "");
        if (normalized.isBlank() || normalized.contains("/") || normalized.contains("\\\\")) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "ARTIFACT_KEY_INVALID", "制品对象 key 非法");
        }
        return normalized;
    }

    private String sha256(byte[] content) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return HexFormat.of().formatHex(digest.digest(content));
        } catch (Exception ex) {
            throw new ApiException(HttpStatus.INTERNAL_SERVER_ERROR, "ARTIFACT_HASH_FAILED", "制品摘要计算失败");
        }
    }

    @Transactional(readOnly = true)
    public Optional<StoredArtifactView> findByOwner(
            StoredArtifactOwnerType ownerType,
            UUID ownerId,
            String artifactType
    ) {
        return repository.findByOwner(ownerType, ownerId, artifactType);
    }

    public boolean objectExists(StoredArtifactView artifact) {
        return artifact != null && objectStorageService.exists(artifact.bucket(), artifact.objectKey());
    }

    private String sha256(Path file) throws IOException {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (java.io.InputStream input = Files.newInputStream(file)) {
                byte[] buffer = new byte[64 * 1024];
                int read;
                while ((read = input.read(buffer)) >= 0) {
                    if (read > 0) {
                        digest.update(buffer, 0, read);
                    }
                }
            }
            return HexFormat.of().formatHex(digest.digest());
        } catch (java.security.NoSuchAlgorithmException ex) {
            throw new ApiException(HttpStatus.INTERNAL_SERVER_ERROR, "ARTIFACT_HASH_FAILED", "制品摘要计算失败");
        }
    }

    private void deletePrevious(StoredArtifactView previous, StoredArtifactView current) {
        if (previous != null && !previous.objectKey().equals(current.objectKey())) {
            objectStorageService.delete(previous.bucket(), previous.objectKey());
        }
    }

    private ApiException notFound(String code, String message) {
        return new ApiException(HttpStatus.NOT_FOUND, code, message);
    }
}
