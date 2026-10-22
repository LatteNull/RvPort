package cn.rvport.backend.artifact;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.when;

import cn.rvport.backend.common.error.ApiException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.junit.jupiter.api.io.TempDir;

@ExtendWith(MockitoExtension.class)
class StoredArtifactServiceTests {

    @TempDir
    private Path tempDir;

    @Mock
    private ObjectStorageService objectStorageService;

    @Mock
    private StoredArtifactRepository repository;

    @Test
    void storesObjectAndMetadataWithSafeKeyAndSha256() {
        StoredArtifactService service = service();
        UUID projectId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        UUID ownerId = UUID.randomUUID();
        byte[] content = "{\"ok\":true}".getBytes(java.nio.charset.StandardCharsets.UTF_8);
        when(repository.findByOwner(StoredArtifactOwnerType.KB_SCAN, ownerId, "SCAN_RESULT_JSON")).thenReturn(Optional.empty());
        when(objectStorageService.put(any(), any(), any())).thenAnswer(invocation ->
                new ObjectStoragePutResult("rvport-artifacts", invocation.getArgument(0), invocation.getArgument(1), content.length)
        );
        when(repository.upsert(any(), any(), any(), any(), any(), any(), any(), any(), any(), any(Long.class), any(), any()))
                .thenAnswer(invocation -> new StoredArtifactView(
                        invocation.getArgument(0),
                        invocation.getArgument(1),
                        invocation.getArgument(2),
                        invocation.getArgument(3),
                        invocation.getArgument(4),
                        invocation.getArgument(5),
                        invocation.getArgument(6),
                        invocation.getArgument(7),
                        invocation.getArgument(8),
                        invocation.getArgument(9),
                        invocation.getArgument(10),
                        Map.of(),
                        OffsetDateTime.now()
                ));

        StoredArtifactView result = service.store(new StoredArtifactCreateCommand(
                projectId,
                taskId,
                StoredArtifactOwnerType.KB_SCAN,
                ownerId,
                "SCAN_RESULT_JSON",
                "application/json",
                content,
                Map.of("count", 1),
                "json"
        ));

        assertThat(result.objectKey()).startsWith("projects/" + projectId + "/kb_scan/" + ownerId + "/scan_result_json-");
        assertThat(result.objectKey()).doesNotContain("\\").doesNotContain("..");
        assertThat(result.sha256()).hasSize(64);
    }

    @Test
    void rejectsUnsafeArtifactTypeBeforeUploading() {
        StoredArtifactService service = service();

        assertThatThrownBy(() -> service.store(new StoredArtifactCreateCommand(
                UUID.randomUUID(),
                UUID.randomUUID(),
                StoredArtifactOwnerType.KB_SCAN,
                UUID.randomUUID(),
                "..",
                "application/json",
                "{}".getBytes(java.nio.charset.StandardCharsets.UTF_8),
                Map.of(),
                "json"
        ))).hasMessage("制品对象 key 非法");
    }

    @Test
    void deletesUploadedObjectWhenMetadataWriteFails() {
        StoredArtifactService service = service();
        UUID ownerId = UUID.randomUUID();
        when(repository.findByOwner(StoredArtifactOwnerType.KB_SCAN, ownerId, "AUDIT_SUMMARY_JSON")).thenReturn(Optional.empty());
        when(objectStorageService.put(any(), any(), any())).thenReturn(new ObjectStoragePutResult(
                "rvport-artifacts",
                "projects/test/object.json",
                "application/json",
                2
        ));
        when(repository.upsert(any(), any(), any(), any(), any(), any(), any(), any(), any(), any(Long.class), any(), any()))
                .thenThrow(new IllegalStateException("db down"));

        assertThatThrownBy(() -> service.storeJson(
                UUID.randomUUID(),
                UUID.randomUUID(),
                StoredArtifactOwnerType.KB_SCAN,
                ownerId,
                "AUDIT_SUMMARY_JSON",
                Map.of("ok", true),
                Map.of()
        )).isInstanceOf(IllegalStateException.class);

        verify(objectStorageService).delete("rvport-artifacts", "projects/test/object.json");
    }

    @Test
    void deletesReplacedObjectAfterSuccessfulUpsert() {
        StoredArtifactService service = service();
        UUID ownerId = UUID.randomUUID();
        StoredArtifactView previous = new StoredArtifactView(
                UUID.randomUUID(),
                UUID.randomUUID(),
                UUID.randomUUID(),
                StoredArtifactOwnerType.KB_SCAN,
                ownerId,
                "AUDIT_SUMMARY_JSON",
                "rvport-artifacts",
                "projects/old/object.json",
                "application/json",
                2,
                "0".repeat(64),
                Map.of(),
                OffsetDateTime.now()
        );
        when(repository.findByOwner(StoredArtifactOwnerType.KB_SCAN, ownerId, "AUDIT_SUMMARY_JSON")).thenReturn(Optional.of(previous));
        when(objectStorageService.put(any(), any(), any())).thenReturn(new ObjectStoragePutResult(
                "rvport-artifacts",
                "projects/new/object.json",
                "application/json",
                2
        ));
        when(repository.upsert(any(), any(), any(), any(), any(), any(), any(), any(), any(), any(Long.class), any(), any()))
                .thenAnswer(invocation -> new StoredArtifactView(
                        invocation.getArgument(0),
                        invocation.getArgument(1),
                        invocation.getArgument(2),
                        invocation.getArgument(3),
                        invocation.getArgument(4),
                        invocation.getArgument(5),
                        invocation.getArgument(6),
                        invocation.getArgument(7),
                        invocation.getArgument(8),
                        invocation.getArgument(9),
                        invocation.getArgument(10),
                        Map.of(),
                        OffsetDateTime.now()
                ));

        service.storeJson(UUID.randomUUID(), UUID.randomUUID(), StoredArtifactOwnerType.KB_SCAN, ownerId,
                "AUDIT_SUMMARY_JSON", Map.of("ok", true), Map.of());

        verify(objectStorageService).delete("rvport-artifacts", "projects/old/object.json");
    }

    @Test
    void rejectsEveryMissingRequiredInputBeforeObjectStorage() {
        byte[] content = new byte[]{1};
        UUID projectId = UUID.randomUUID();
        UUID ownerId = UUID.randomUUID();
        List<StoredArtifactCreateCommand> invalid = List.of(
                new StoredArtifactCreateCommand(null, null, StoredArtifactOwnerType.KB_SCAN, ownerId,
                        "TYPE", "application/json", content, Map.of(), "json"),
                new StoredArtifactCreateCommand(projectId, null, null, ownerId,
                        "TYPE", "application/json", content, Map.of(), "json"),
                new StoredArtifactCreateCommand(projectId, null, StoredArtifactOwnerType.KB_SCAN, null,
                        "TYPE", "application/json", content, Map.of(), "json"),
                new StoredArtifactCreateCommand(projectId, null, StoredArtifactOwnerType.KB_SCAN, ownerId,
                        null, "application/json", content, Map.of(), "json"),
                new StoredArtifactCreateCommand(projectId, null, StoredArtifactOwnerType.KB_SCAN, ownerId,
                        " ", "application/json", content, Map.of(), "json"),
                new StoredArtifactCreateCommand(projectId, null, StoredArtifactOwnerType.KB_SCAN, ownerId,
                        "TYPE", null, content, Map.of(), "json"),
                new StoredArtifactCreateCommand(projectId, null, StoredArtifactOwnerType.KB_SCAN, ownerId,
                        "TYPE", " ", content, Map.of(), "json"),
                new StoredArtifactCreateCommand(projectId, null, StoredArtifactOwnerType.KB_SCAN, ownerId,
                        "TYPE", "application/json", null, Map.of(), "json")
        );

        invalid.forEach(command -> assertThatThrownBy(() -> service().store(command))
                .isInstanceOf(ApiException.class)
                .extracting("code")
                .isEqualTo("ARTIFACT_INPUT_INVALID"));
        verify(objectStorageService, never()).put(any(), any(), any());
    }

    @Test
    void usesBinaryExtensionDefaultAndNormalizesSafeObjectKeyTokens() {
        UUID projectId = UUID.randomUUID();
        UUID ownerId = UUID.randomUUID();
        byte[] content = new byte[]{1};
        when(repository.findByOwner(StoredArtifactOwnerType.KB_SCAN, ownerId, "..TYPE..NAME.."))
                .thenReturn(Optional.empty());
        when(objectStorageService.put(any(), any(), any())).thenAnswer(invocation ->
                new ObjectStoragePutResult("bucket", invocation.getArgument(0), invocation.getArgument(1), 1));
        when(repository.upsert(any(), any(), any(), any(), any(), any(), any(), any(), any(), any(Long.class), any(), any()))
                .thenAnswer(invocation -> artifactFromInvocation(invocation));

        StoredArtifactView nullExtension = service().store(new StoredArtifactCreateCommand(
                projectId, null, StoredArtifactOwnerType.KB_SCAN, ownerId, "..TYPE..NAME..",
                "application/octet-stream", content, Map.of(), null));
        assertThat(nullExtension.objectKey()).contains("/type.name-").endsWith(".bin");

        when(repository.findByOwner(StoredArtifactOwnerType.KB_SCAN, ownerId, "TYPE TWO"))
                .thenReturn(Optional.empty());
        StoredArtifactView blankExtension = service().store(new StoredArtifactCreateCommand(
                projectId, null, StoredArtifactOwnerType.KB_SCAN, ownerId, "TYPE TWO",
                "application/octet-stream", content, Map.of(), " "));
        assertThat(blankExtension.objectKey()).contains("/type_two-").endsWith(".bin");
    }

    @Test
    void storesFileAndDownloadsItsBytes() throws Exception {
        UUID projectId = UUID.randomUUID();
        UUID ownerId = UUID.randomUUID();
        UUID artifactId = UUID.randomUUID();
        Path file = tempDir.resolve("report.txt");
        Files.writeString(file, "report");
        when(repository.findByOwner(StoredArtifactOwnerType.KB_SCAN, ownerId, "REPORT")).thenReturn(Optional.empty());
        when(objectStorageService.put(any(), any(), any())).thenAnswer(invocation ->
                new ObjectStoragePutResult("bucket", invocation.getArgument(0), invocation.getArgument(1), 6));
        when(repository.upsert(any(), any(), any(), any(), any(), any(), any(), any(), any(), any(Long.class), any(), any()))
                .thenAnswer(this::artifactFromInvocation);

        StoredArtifactView stored = service().storeFile(projectId, null, StoredArtifactOwnerType.KB_SCAN,
                ownerId, "REPORT", file, "text/plain", Map.of(), "txt");
        StoredArtifactView lookup = new StoredArtifactView(artifactId, projectId, null, StoredArtifactOwnerType.KB_SCAN,
                ownerId, "REPORT", stored.bucket(), stored.objectKey(), "text/plain", 6, "sha", Map.of(), OffsetDateTime.now());
        when(repository.findById(artifactId)).thenReturn(Optional.of(lookup));
        when(objectStorageService.get(stored.bucket(), stored.objectKey())).thenReturn(
                new ObjectStorageObject(stored.bucket(), stored.objectKey(), "text/plain", 6, "report".getBytes()));

        assertThat(service().download(artifactId).resource().getContentAsString(java.nio.charset.StandardCharsets.UTF_8))
                .isEqualTo("report");
    }

    @Test
    void streamsLargeFileAndExposesSafeOwnerLookup() throws Exception {
        UUID projectId = UUID.randomUUID();
        UUID ownerId = UUID.randomUUID();
        Path file = tempDir.resolve("bundle.tgz");
        Files.writeString(file, "large-bundle");
        when(repository.findByOwner(StoredArtifactOwnerType.BUILD_VALIDATION, ownerId, "BUNDLE"))
                .thenReturn(Optional.empty());
        when(objectStorageService.putFile(any(), any(), eq(file))).thenAnswer(invocation ->
                new ObjectStoragePutResult("bucket", invocation.getArgument(0), invocation.getArgument(1),
                        Files.size(file)));
        when(repository.upsert(any(), any(), any(), any(), any(), any(), any(), any(), any(), any(Long.class), any(), any()))
                .thenAnswer(this::artifactFromInvocation);

        StoredArtifactView stored = service().storeLargeFile(projectId, null,
                StoredArtifactOwnerType.BUILD_VALIDATION, ownerId, "BUNDLE", file,
                "application/gzip", Map.of("kind", "bitcode"), "tgz");

        assertThat(stored.sizeBytes()).isEqualTo(Files.size(file));
        assertThat(stored.sha256()).hasSize(64);
        verify(objectStorageService).putFile(any(), eq("application/gzip"), eq(file));

        when(repository.findByOwner(StoredArtifactOwnerType.BUILD_VALIDATION, ownerId, "BUNDLE"))
                .thenReturn(Optional.of(stored));
        when(objectStorageService.exists(stored.bucket(), stored.objectKey())).thenReturn(true);
        assertThat(service().findByOwner(StoredArtifactOwnerType.BUILD_VALIDATION, ownerId, "BUNDLE"))
                .contains(stored);
        assertThat(service().objectExists(stored)).isTrue();
        assertThat(service().objectExists(null)).isFalse();
        when(objectStorageService.exists(stored.bucket(), stored.objectKey())).thenReturn(false);
        assertThat(service().objectExists(stored)).isFalse();
    }

    @Test
    void rejectsEveryMissingRequiredLargeFileInput() throws Exception {
        UUID projectId = UUID.randomUUID();
        UUID ownerId = UUID.randomUUID();
        Path file = tempDir.resolve("bundle.tgz");
        Files.writeString(file, "bundle");
        Object[][] invalid = {
                {null, StoredArtifactOwnerType.BUILD_VALIDATION, ownerId, "BUNDLE", "application/gzip", file},
                {projectId, null, ownerId, "BUNDLE", "application/gzip", file},
                {projectId, StoredArtifactOwnerType.BUILD_VALIDATION, null, "BUNDLE", "application/gzip", file},
                {projectId, StoredArtifactOwnerType.BUILD_VALIDATION, ownerId, null, "application/gzip", file},
                {projectId, StoredArtifactOwnerType.BUILD_VALIDATION, ownerId, " ", "application/gzip", file},
                {projectId, StoredArtifactOwnerType.BUILD_VALIDATION, ownerId, "BUNDLE", null, file},
                {projectId, StoredArtifactOwnerType.BUILD_VALIDATION, ownerId, "BUNDLE", " ", file},
                {projectId, StoredArtifactOwnerType.BUILD_VALIDATION, ownerId, "BUNDLE", "application/gzip", null}
        };
        for (Object[] value : invalid) {
            assertThatThrownBy(() -> service().storeLargeFile(
                    (UUID) value[0], null, (StoredArtifactOwnerType) value[1], (UUID) value[2],
                    (String) value[3], (Path) value[5], (String) value[4], Map.of(), "tgz"))
                    .isInstanceOf(ApiException.class)
                    .extracting("code").isEqualTo("ARTIFACT_INPUT_INVALID");
        }
        verify(objectStorageService, never()).putFile(any(), any(), any());
    }

    @Test
    void largeFileReplacementWithSameObjectKeyDoesNotDeleteCurrentObject() throws Exception {
        UUID projectId = UUID.randomUUID();
        UUID ownerId = UUID.randomUUID();
        Path file = tempDir.resolve("same.tgz");
        Files.writeString(file, "bundle");
        StoredArtifactView previous = artifactView(UUID.randomUUID(), "same-key");
        when(repository.findByOwner(StoredArtifactOwnerType.BUILD_VALIDATION, ownerId, "BUNDLE"))
                .thenReturn(Optional.of(previous));
        when(objectStorageService.putFile(any(), any(), eq(file))).thenReturn(
                new ObjectStoragePutResult(previous.bucket(), previous.objectKey(), "application/gzip", 6));
        when(repository.upsert(any(), any(), any(), any(), any(), any(), any(), any(), any(), any(Long.class), any(), any()))
                .thenAnswer(invocation -> new StoredArtifactView(invocation.getArgument(0), projectId, null,
                        StoredArtifactOwnerType.BUILD_VALIDATION, ownerId, "BUNDLE", previous.bucket(),
                        previous.objectKey(), "application/gzip", 6, invocation.getArgument(10), Map.of(),
                        OffsetDateTime.now()));

        service().storeLargeFile(projectId, null, StoredArtifactOwnerType.BUILD_VALIDATION, ownerId,
                "BUNDLE", file, "application/gzip", Map.of(), "tgz");

        verify(objectStorageService, never()).delete(previous.bucket(), previous.objectKey());
    }

    @Test
    void downloadMapsMissingMetadataAndMissingObjectSeparately() {
        UUID missing = UUID.randomUUID();
        assertThatThrownBy(() -> service().download(missing)).isInstanceOf(ApiException.class)
                .extracting("code").isEqualTo("ARTIFACT_NOT_FOUND");

        StoredArtifactView artifact = artifactView(UUID.randomUUID(), "same-key");
        when(repository.findById(artifact.id())).thenReturn(Optional.of(artifact));
        when(objectStorageService.get(artifact.bucket(), artifact.objectKey()))
                .thenThrow(new ObjectStorageException("missing", null));
        assertThatThrownBy(() -> service().download(artifact.id())).isInstanceOf(ApiException.class)
                .extracting("code").isEqualTo("ARTIFACT_OBJECT_NOT_FOUND");
    }

    @Test
    void deleteIsIdempotentAndReplacementWithSameKeyIsNotDeleted() {
        UUID absent = UUID.randomUUID();
        service().delete(absent);
        verify(objectStorageService, never()).delete(any(), any());

        StoredArtifactView artifact = artifactView(UUID.randomUUID(), "same-key");
        when(repository.findById(artifact.id())).thenReturn(Optional.of(artifact));
        service().delete(artifact.id());
        verify(objectStorageService).delete(artifact.bucket(), artifact.objectKey());
        verify(repository).delete(artifact.id());
    }

    private StoredArtifactView artifactFromInvocation(org.mockito.invocation.InvocationOnMock invocation) {
        return new StoredArtifactView(invocation.getArgument(0), invocation.getArgument(1), invocation.getArgument(2),
                invocation.getArgument(3), invocation.getArgument(4), invocation.getArgument(5), invocation.getArgument(6),
                invocation.getArgument(7), invocation.getArgument(8), invocation.getArgument(9), invocation.getArgument(10),
                Map.of(), OffsetDateTime.now());
    }

    private StoredArtifactView artifactView(UUID id, String objectKey) {
        return new StoredArtifactView(id, UUID.randomUUID(), null, StoredArtifactOwnerType.KB_SCAN,
                UUID.randomUUID(), "TYPE", "bucket", objectKey, "text/plain", 1, "sha", Map.of(), OffsetDateTime.now());
    }

    @Test
    void guardedFileStreamsContentAndValidatesPathBeforeUpload() throws Exception {
        var context = org.mockito.Mockito.mock(cn.rvport.backend.worker.TaskExecutionContext.class);
        when(context.publish(any())).thenAnswer(invocation -> invocation.<java.util.function.Supplier<?>>getArgument(0).get());
        Path file = tempDir.resolve("guarded.json");
        Files.writeString(file, "{}");
        when(objectStorageService.putFile(any(), any(), eq(file))).thenReturn(new ObjectStoragePutResult("bucket", "new", "application/json", 2));
        when(repository.upsert(any(), any(), any(), any(), any(), any(), any(), any(), any(), any(Long.class), any(), any()))
                .thenAnswer(this::artifactFromInvocation);
        UUID project = UUID.randomUUID();
        UUID owner = UUID.randomUUID();
        assertThatThrownBy(() -> service().storeLargeFile(project, null, StoredArtifactOwnerType.KB_SCAN, owner,
                "TYPE", null, "application/json", Map.of(), "json", context))
                .isInstanceOf(ApiException.class).extracting("code").isEqualTo("ARTIFACT_INPUT_INVALID");
        assertThat(service().storeFile(project, null, StoredArtifactOwnerType.KB_SCAN, owner,
                "TYPE", file, "application/json", Map.of(), "json", context).sha256()).hasSize(64);
        verify(objectStorageService).putFile(any(), eq("application/json"), eq(file));
    }

    @Test
    void guardedDeletePreservesReplacementAndWaitsForCommit() {
        var context = org.mockito.Mockito.mock(cn.rvport.backend.worker.TaskExecutionContext.class);
        when(context.publish(any())).thenAnswer(invocation -> invocation.<java.util.function.Supplier<?>>getArgument(0).get());
        StoredArtifactView expected = artifactView(UUID.randomUUID(), "old");
        when(repository.findById(expected.id())).thenReturn(Optional.empty(), Optional.of(artifactView(expected.id(), "new")), Optional.of(expected));
        service().delete(expected, context);
        service().delete(expected, context);
        verify(repository, never()).delete(any());
        verify(objectStorageService, never()).delete(any(), any());
        org.springframework.transaction.support.TransactionSynchronizationManager.initSynchronization();
        try {
            service().delete(expected, context);
            verify(repository).delete(expected.id());
            verify(objectStorageService, never()).delete(any(), any());
            org.springframework.transaction.support.TransactionSynchronizationManager.getSynchronizations().forEach(sync -> sync.afterCommit());
            verify(objectStorageService).delete(expected.bucket(), "old");
        } finally {
            org.springframework.transaction.support.TransactionSynchronizationManager.clearSynchronization();
        }
        org.mockito.Mockito.clearInvocations(objectStorageService);
        service().delete(expected, context);
        verify(objectStorageService).delete(expected.bucket(), "old");
    }

    private StoredArtifactService service() {
        return new StoredArtifactService(objectStorageService, repository, new ObjectMapper());
    }

    @Test
    void revokedAttemptCleansOnlyItsNewUploadEvenIfCleanupFails() {
        var context = org.mockito.Mockito.mock(cn.rvport.backend.worker.TaskExecutionContext.class);
        when(objectStorageService.put(any(), any(), any())).thenReturn(
                new ObjectStoragePutResult("bucket", "new-object", "application/json", 2));
        when(context.publish(any())).thenThrow(new cn.rvport.backend.worker.TaskAttemptLostException());
        org.mockito.Mockito.doThrow(new IllegalStateException("storage unavailable"))
                .when(objectStorageService).delete("bucket", "new-object");

        assertThatThrownBy(() -> service().storeJson(UUID.randomUUID(), UUID.randomUUID(),
                StoredArtifactOwnerType.KB_SCAN, UUID.randomUUID(), "TYPE", Map.of(), Map.of(), context))
                .isInstanceOf(cn.rvport.backend.worker.TaskAttemptLostException.class);
        org.mockito.Mockito.verifyNoInteractions(repository);
        verify(objectStorageService).delete("bucket", "new-object");
    }

    @Test
    void guardedPublicationDefersObjectCleanupUntilTransactionOutcome() {
        var context = org.mockito.Mockito.mock(cn.rvport.backend.worker.TaskExecutionContext.class);
        when(context.publish(any())).thenAnswer(invocation -> invocation.<java.util.function.Supplier<?>>getArgument(0).get());
        when(objectStorageService.put(any(), any(), any())).thenReturn(
                new ObjectStoragePutResult("bucket", "new-object", "application/json", 2));
        when(repository.findByOwner(any(), any(), any())).thenReturn(Optional.of(artifactView(UUID.randomUUID(), "old-object")));
        when(repository.upsert(any(), any(), any(), any(), any(), any(), any(), any(), any(), any(Long.class), any(), any()))
                .thenAnswer(this::artifactFromInvocation);
        for (int status : new int[]{0, 1, 2}) {
            org.mockito.Mockito.clearInvocations(objectStorageService);
            org.springframework.transaction.support.TransactionSynchronizationManager.initSynchronization();
            try {
                var result = service().storeJson(UUID.randomUUID(), UUID.randomUUID(), StoredArtifactOwnerType.KB_SCAN,
                        UUID.randomUUID(), "TYPE", Map.of(), Map.of(), context);
                assertThat(result.objectKey()).isEqualTo("new-object");
                verify(objectStorageService, never()).delete(any(), any());
                org.springframework.transaction.support.TransactionSynchronizationManager.getSynchronizations()
                        .forEach(sync -> sync.afterCompletion(status));
                if (status == 0) {
                    verify(objectStorageService).delete("bucket", "old-object");
                    verify(objectStorageService, never()).delete("bucket", "new-object");
                } else if (status == 1) {
                    verify(objectStorageService).delete("bucket", "new-object");
                    verify(objectStorageService, never()).delete("bucket", "old-object");
                } else {
                    verify(objectStorageService, never()).delete(any(), any());
                }
            } finally {
                org.springframework.transaction.support.TransactionSynchronizationManager.clearSynchronization();
            }
        }
    }

    @Test
    void guardedPublicationWithoutTransactionSupportsNoPreviousAndSameObject() {
        var context = org.mockito.Mockito.mock(cn.rvport.backend.worker.TaskExecutionContext.class);
        when(context.publish(any())).thenAnswer(invocation -> invocation.<java.util.function.Supplier<?>>getArgument(0).get());
        when(objectStorageService.put(any(), any(), any())).thenReturn(new ObjectStoragePutResult("bucket", "same", "application/json", 2));
        when(repository.findByOwner(any(), any(), any())).thenReturn(Optional.empty(), Optional.of(artifactView(UUID.randomUUID(), "same")));
        when(repository.upsert(any(), any(), any(), any(), any(), any(), any(), any(), any(), any(Long.class), any(), any()))
                .thenAnswer(this::artifactFromInvocation);
        for (int i = 0; i < 2; i++) {
            assertThat(service().storeJson(UUID.randomUUID(), UUID.randomUUID(), StoredArtifactOwnerType.KB_SCAN,
                    UUID.randomUUID(), "TYPE", Map.of(), Map.of(), context).sha256()).hasSize(64);
        }
        verify(objectStorageService, never()).delete(any(), any());
    }

    @Test
    void guardedJsonRejectsInvalidSerializationBeforeUpload() throws Exception {
        ObjectMapper mapper = org.mockito.Mockito.mock(ObjectMapper.class);
        when(mapper.writeValueAsBytes(any())).thenThrow(new com.fasterxml.jackson.core.JsonProcessingException("bad") { });
        assertThatThrownBy(() -> new StoredArtifactService(objectStorageService, repository, mapper).storeJson(
                UUID.randomUUID(), UUID.randomUUID(), StoredArtifactOwnerType.KB_SCAN, UUID.randomUUID(), "TYPE",
                Map.of(), Map.of(), org.mockito.Mockito.mock(cn.rvport.backend.worker.TaskExecutionContext.class)))
                .isInstanceOf(ApiException.class).extracting("code").isEqualTo("ARTIFACT_CONTENT_INVALID");
        org.mockito.Mockito.verifyNoInteractions(objectStorageService, repository);
    }
}
