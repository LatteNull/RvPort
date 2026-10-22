package cn.rvport.backend.buildvalidation.bitcode;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.contains;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.artifact.ObjectStorageException;
import cn.rvport.backend.artifact.StoredArtifactOwnerType;
import cn.rvport.backend.artifact.StoredArtifactService;
import cn.rvport.backend.artifact.StoredArtifactView;
import cn.rvport.backend.config.RvPortProperties;
import cn.rvport.backend.credential.CredentialKind;
import cn.rvport.backend.environment.runtime.SshClientAdapter;
import cn.rvport.backend.environment.runtime.SshCommandResult;
import cn.rvport.backend.environment.runtime.SshConnectionTarget;
import cn.rvport.backend.environment.runtime.SshRuntimeCredential;
import cn.rvport.backend.task.TaskErrorCode;
import cn.rvport.backend.task.TaskLogType;
import cn.rvport.backend.worker.TaskExecutionContext;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicReference;
import org.apache.commons.compress.archivers.tar.TarArchiveEntry;
import org.apache.commons.compress.archivers.tar.TarArchiveOutputStream;
import org.apache.commons.compress.compressors.gzip.GzipCompressorOutputStream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.test.util.ReflectionTestUtils;

class BitcodeArtifactServiceTests {

    @TempDir
    Path tempDir;
    private final ObjectMapper mapper = new ObjectMapper().findAndRegisterModules();

    @Test
    void disabledDoesNotTouchExternalSystems() {
        Collaborators c = collaborators(false);

        BitcodeGenerationResult result = c.service.generate(c.request);

        assertThat(result.summary().status()).isEqualTo(BitcodeStatus.NOT_ATTEMPTED);
        verify(c.toolchain, never()).ensure(any());
    }

    @Test
    void reusesStoredV2AndExposesSafeDigestSummary() {
        Collaborators c = collaborators(true);
        Map<String, Object> summary = summary(2, 2, 0, 0);
        StoredArtifactView manifest = artifact(c.request, "LLVM_BITCODE_MANIFEST_JSON", summary);
        StoredArtifactView bundle = artifact(c.request, "LLVM_BITCODE_BUNDLE_TGZ", summary);
        when(c.storage.findByOwner(any(), any(), org.mockito.ArgumentMatchers.eq("LLVM_BITCODE_MANIFEST_JSON")))
                .thenReturn(Optional.of(manifest));
        when(c.storage.findByOwner(any(), any(), org.mockito.ArgumentMatchers.eq("LLVM_BITCODE_BUNDLE_TGZ")))
                .thenReturn(Optional.of(bundle));
        when(c.storage.objectExists(manifest)).thenReturn(true);
        when(c.storage.objectExists(bundle)).thenReturn(true);

        BitcodeGenerationResult result = c.service.generate(c.request);

        assertThat(result.summary().status()).isEqualTo(BitcodeStatus.READY);
        assertThat(result.summary().legacy()).isFalse();
        assertThat(result.summary().sourceIdentityDigest()).isEqualTo(BitcodeTestFixtures.HASH_B);
        assertThat(result.artifacts()).containsExactly(manifest, bundle);
        verify(c.toolchain, never()).ensure(any());
    }

    @Test
    void reusesPartialAndFailedStoredV2WithCorrectStatus() {
        for (Map<String, Object> summary : List.of(summary(3, 1, 1, 1), summary(2, 0, 1, 1))) {
            Collaborators c = collaborators(true);
            StoredArtifactView manifest = artifact(c.request, "LLVM_BITCODE_MANIFEST_JSON", summary);
            StoredArtifactView bundle = artifact(c.request, "LLVM_BITCODE_BUNDLE_TGZ", summary);
            when(c.storage.findByOwner(any(), any(), any())).thenReturn(Optional.of(manifest), Optional.of(bundle));
            when(c.storage.objectExists(any())).thenReturn(true);

            BitcodeGenerationResult result = c.service.generate(c.request);

            assertThat(result.summary().status()).isIn(BitcodeStatus.PARTIAL, BitcodeStatus.FAILED);
            assertThat(result.summary().reasonCode()).isEqualTo(BitcodeReasonCode.TRANSLATION_UNIT_FAILED);
        }
    }

    @Test
    void doesNotReuseLegacyOrMissingObjects() {
        for (Map<String, Object> summary : List.of(
                Map.<String, Object>of("schemaVersion", "llvm-bitcode-artifact-set.v1", "toolchainId", "llvm-test",
                        "toolchainVersion", "21.1.8"),
                Map.<String, Object>of("schemaVersion", BitcodeManifest.SCHEMA_VERSION, "toolchainId", "wrong",
                        "toolchainVersion", "21.1.8"))) {
            Collaborators c = collaborators(true);
            StoredArtifactView manifest = artifact(c.request, "LLVM_BITCODE_MANIFEST_JSON", summary);
            StoredArtifactView bundle = artifact(c.request, "LLVM_BITCODE_BUNDLE_TGZ", summary);
            when(c.storage.findByOwner(any(), any(), any())).thenReturn(Optional.of(manifest), Optional.of(bundle));
            when(c.storage.objectExists(any())).thenReturn(true);
            when(c.toolchain.ensure(any())).thenThrow(new BitcodeRuntimeException(
                    BitcodeReasonCode.TOOLCHAIN_BUNDLE_UNAVAILABLE, "missing"));
            assertThat(c.service.generate(c.request).summary().reasonCode())
                    .isEqualTo(BitcodeReasonCode.TOOLCHAIN_BUNDLE_UNAVAILABLE);
        }
        Collaborators missingObject = collaborators(true);
        StoredArtifactView manifest = artifact(missingObject.request, "manifest", summary(1, 1, 0, 0));
        StoredArtifactView bundle = artifact(missingObject.request, "bundle", summary(1, 1, 0, 0));
        when(missingObject.storage.findByOwner(any(), any(), any()))
                .thenReturn(Optional.of(manifest), Optional.of(bundle));
        when(missingObject.storage.objectExists(manifest)).thenReturn(true);
        when(missingObject.storage.objectExists(bundle)).thenReturn(false);
        when(missingObject.toolchain.ensure(any())).thenThrow(new BitcodeRuntimeException(
                BitcodeReasonCode.TOOLCHAIN_BUNDLE_UNAVAILABLE, "missing"));
        assertThat(missingObject.service.generate(missingObject.request).summary().reasonCode())
                .isEqualTo(BitcodeReasonCode.TOOLCHAIN_BUNDLE_UNAVAILABLE);
    }

    @Test
    void reportsProducerPreparationFailureAndZeroTranslationUnits() throws Exception {
        Collaborators transfer = collaborators(true);
        when(transfer.toolchain.ensure(any())).thenReturn(toolchain());
        when(transfer.ssh.execute(any())).thenReturn(new SshCommandResult(2, "", "bad", Duration.ZERO), ok());
        assertThat(transfer.service.generate(transfer.request).summary().reasonCode())
                .isEqualTo(BitcodeReasonCode.TRANSFER_FAILED);

        BitcodeManifest valid = BitcodeTestFixtures.manifest(List.of(BitcodeTestFixtures.failed(
                "placeholder", "src/main.c")));
        BitcodeManifest empty = new BitcodeManifest(valid.kind(), valid.schemaVersion(), valid.artifactSetId(),
                valid.sourceIdentityDigest(), valid.compileContext(), valid.producer(), "FAILED",
                new BitcodeManifest.Counts(0, 0, 0, 0, 0, 0), List.of(), valid.scopes(),
                valid.generatedAt(), valid.semanticDigest());
        Collaborators zero = configuredGeneration(empty, new byte[0], 0);
        assertThat(zero.service.generate(zero.request).summary().reasonCode())
                .isEqualTo(BitcodeReasonCode.NO_C_CPP_TRANSLATION_UNITS);
    }

    @Test
    void generatesValidV2StoresBothArtifactsAndKeepsBusinessIdsOutOfManifest() throws Exception {
        byte[] bc = "real-bitcode".getBytes(StandardCharsets.UTF_8);
        BitcodeManifest manifest = BitcodeTestFixtures.manifest(List.of(BitcodeTestFixtures.produced(
                "record", "src/main.c", bc.length, sha(bc))));
        Collaborators c = configuredGeneration(manifest, bc, 0);
        StoredArtifactView manifestArtifact = artifact(c.request, "LLVM_BITCODE_MANIFEST_JSON", Map.of());
        StoredArtifactView bundleArtifact = artifact(c.request, "LLVM_BITCODE_BUNDLE_TGZ", Map.of());
        when(c.storage.store(any(), any())).thenReturn(manifestArtifact);
        when(c.storage.storeLargeFile(any(), any(), any(), any(), any(), any(), any(), any(), any(), any()))
                .thenReturn(bundleArtifact);

        BitcodeGenerationResult result = c.service.generate(c.request);

        assertThat(result.summary().status()).isEqualTo(BitcodeStatus.READY);
        assertThat(result.summary().artifactSetId()).isEqualTo(manifest.artifactSetId());
        assertThat(result.summary().bundleSha256()).hasSize(64);
        assertThat(result.summary().toMap()).doesNotContainKeys("projectId", "buildRunId", "sourceRevisionId");
        verify(c.storage).store(any(), any());
        verify(c.storage).storeLargeFile(any(), any(), any(), any(), any(), any(), any(), any(), any(), any());
    }

    @Test
    void preservesPartialAndFailedPlannedDenominator() throws Exception {
        byte[] bc = "real-bitcode".getBytes(StandardCharsets.UTF_8);
        BitcodeManifest partial = BitcodeTestFixtures.manifest(List.of(
                BitcodeTestFixtures.produced("ok", "src/a.c", bc.length, sha(bc)),
                BitcodeTestFixtures.failed("bad", "src/b.c"),
                BitcodeTestFixtures.missing("duplicate", "src/c.c")));
        Collaborators c = configuredGeneration(partial, bc, 0);
        when(c.storage.store(any(), any())).thenReturn(artifact(c.request, "manifest", Map.of()));
        when(c.storage.storeLargeFile(any(), any(), any(), any(), any(), any(), any(), any(), any(), any()))
                .thenReturn(artifact(c.request, "bundle", Map.of()));

        BitcodeGenerationResult result = c.service.generate(c.request);

        assertThat(result.summary().status()).isEqualTo(BitcodeStatus.PARTIAL);
        assertThat(result.summary().plannedCount()).isEqualTo(3);
        assertThat(result.summary().failedCount()).isOne();
        assertThat(result.summary().skippedCount()).isOne();
    }

    @Test
    void isolatesProducerValidationTransferAndStorageFailures() throws Exception {
        Collaborators producer = collaborators(true);
        when(producer.toolchain.ensure(any())).thenReturn(toolchain());
        when(producer.ssh.execute(any())).thenReturn(ok(), new SshCommandResult(2, "", "bad", Duration.ZERO), ok());
        assertThat(producer.service.generate(producer.request).summary().reasonCode())
                .isEqualTo(BitcodeReasonCode.TRANSLATION_UNIT_FAILED);

        byte[] bc = "real-bitcode".getBytes(StandardCharsets.UTF_8);
        BitcodeManifest wrongProducer = BitcodeTestFixtures.manifest(List.of(BitcodeTestFixtures.produced(
                "record", "src/main.c", bc.length, sha(bc))));
        BitcodeManifest tampered = new BitcodeManifest(wrongProducer.kind(), wrongProducer.schemaVersion(),
                wrongProducer.artifactSetId(), wrongProducer.sourceIdentityDigest(), wrongProducer.compileContext(),
                new BitcodeManifest.Producer("clang", "20", "20", "x86_64"), wrongProducer.status(),
                wrongProducer.counts(), wrongProducer.records(), wrongProducer.scopes(), wrongProducer.generatedAt(),
                wrongProducer.semanticDigest());
        Collaborators invalid = configuredGeneration(tampered, bc, 0);
        assertThat(invalid.service.generate(invalid.request).summary().reasonCode())
                .isEqualTo(BitcodeReasonCode.MANIFEST_INVALID);

        Collaborators storage = configuredGeneration(wrongProducer, bc, 0);
        when(storage.storage.store(any(), any())).thenThrow(new ObjectStorageException("down", null));
        assertThat(storage.service.generate(storage.request).summary().reasonCode())
                .isEqualTo(BitcodeReasonCode.STORAGE_FAILED);
    }

    @Test
    void reportsGenericFailureTypeWhenExceptionHasNoMessage() {
        Collaborators c = collaborators(true);
        when(c.toolchain.ensure(any())).thenThrow(new IllegalStateException());

        BitcodeGenerationResult result = c.service.generate(c.request);

        assertThat(result.summary().reasonCode()).isEqualTo(BitcodeReasonCode.INTERNAL_ERROR);
        verify(c.request.executionContext()).log(eq(TaskLogType.STDERR),
                contains("IllegalStateException"));
    }

    @Test
    void deletesManifestWhenBundleStorageFailsAfterPartialUpload() throws Exception {
        byte[] bc = "real-bitcode".getBytes(StandardCharsets.UTF_8);
        BitcodeManifest manifest = BitcodeTestFixtures.manifest(List.of(BitcodeTestFixtures.produced(
                "record", "src/main.c", bc.length, sha(bc))));
        Collaborators c = configuredGeneration(manifest, bc, 0);
        StoredArtifactView manifestArtifact = artifact(c.request, "LLVM_BITCODE_MANIFEST_JSON", Map.of());
        when(c.storage.store(any(), any())).thenReturn(manifestArtifact);
        when(c.storage.storeLargeFile(any(), any(), any(), any(), any(), any(), any(), any(), any(), any()))
                .thenThrow(new ObjectStorageException("bundle upload failed", null));

        BitcodeGenerationResult result = c.service.generate(c.request);

        assertThat(result.summary().reasonCode()).isEqualTo(BitcodeReasonCode.STORAGE_FAILED);
        verify(c.storage).delete(eq(manifestArtifact), any());
    }

    @Test
    void strictBundleValidationRejectsUnknownTraversalLinkDuplicateAndHashMismatch() throws Exception {
        byte[] bc = "real-bitcode".getBytes(StandardCharsets.UTF_8);
        BitcodeManifest manifest = BitcodeTestFixtures.manifest(List.of(BitcodeTestFixtures.produced(
                "record", "src/main.c", bc.length, sha(bc))));
        Path manifestPath = writeManifest(manifest);
        BitcodeManifest.ArtifactRecord record = manifest.records().getFirst();
        List<Entry> required = required(manifest, bc, Files.readAllBytes(manifestPath));
        invoke(service(64 * 1024, 1024 * 1024), "validateBundle", manifest, manifestPath,
                writeBundle("valid.tgz", required));

        for (List<Entry> entries : List.of(
                List.of(entry("manifest.json", Files.readAllBytes(manifestPath)), entry("../escape", bc)),
                List.of(entry("manifest.json", Files.readAllBytes(manifestPath)), entry("unknown", bc)),
                List.of(link("records/link.json", "target")),
                List.of(entry("manifest.json", Files.readAllBytes(manifestPath)),
                        entry("manifest.json", Files.readAllBytes(manifestPath))),
                List.of(entry("manifest.json", "wrong".getBytes(StandardCharsets.UTF_8))),
                List.of(entry("manifest.json", Files.readAllBytes(manifestPath)),
                        entry("records/" + record.recordId() + ".json", "{}".getBytes(StandardCharsets.UTF_8))),
                List.of(entry("manifest.json", Files.readAllBytes(manifestPath)),
                        entry(record.bitcode().path(), "wrong".getBytes(StandardCharsets.UTF_8))))) {
            assertThatThrownBy(() -> invoke(service(64 * 1024, 1024 * 1024), "validateBundle", manifest, manifestPath,
                    writeBundle(UUID.randomUUID() + ".tgz", entries)))
                    .isInstanceOf(BitcodeRuntimeException.class);
        }
        assertThatThrownBy(() -> invoke(service(64 * 1024, 8), "validateBundle", manifest, manifestPath,
                writeBundle("oversized.tgz", required)))
                .isInstanceOf(BitcodeRuntimeException.class);
    }

    @Test
    void utilityBranchesClassifyAndSanitizeWithoutLeakingPaths() {
        BitcodeArtifactService service = service(1024, 4096);
        assertThat((Integer) invoke(service, "number", null, "x")).isZero();
        assertThat((Integer) invoke(service, "number", Map.of("x", "9"), "x")).isZero();
        assertThat((Long) invoke(service, "longNumber", null, "x")).isZero();
        assertThat((Long) invoke(service, "longNumber", Map.of("x", "9"), "x")).isZero();
        assertThat((Long) invoke(service, "longNumber", Map.of("x", 9), "x")).isEqualTo(9L);
        assertThat((String) invoke(service, "string", null, "x")).isNull();
        assertThat((String) invoke(service, "string", Map.of("x", "v"), "x")).isEqualTo("v");
        assertThat((String) invoke(service, "string", Map.of("x", 9), "x")).isEqualTo("9");
        assertThat((String) invoke(service, "safeMessage", (Object) null)).isEmpty();
        assertThat((String) invoke(service, "safeMessage", "/tmp/secret failed")).doesNotContain("/tmp/secret");
        assertThat((String) invoke(service, "joinRemote", "/a/", "/b")).isEqualTo("/a/b");
        assertThat((String) invoke(service, "shellQuote", "a'b")).isEqualTo("'a'\"'\"'b'");
        assertThat((BitcodeReasonCode) invoke(service, "classify", new IllegalArgumentException()))
                .isEqualTo(BitcodeReasonCode.MANIFEST_INVALID);
        assertThat((BitcodeReasonCode) invoke(service, "classify",
                new cn.rvport.backend.environment.runtime.SshRuntimeException(
                        TaskErrorCode.HANDLER_FAILED, "bad", null))).isEqualTo(BitcodeReasonCode.TRANSFER_FAILED);
        assertThat((BitcodeReasonCode) invoke(service, "classify", new ObjectStorageException("bad", null)))
                .isEqualTo(BitcodeReasonCode.STORAGE_FAILED);
        assertThat((BitcodeReasonCode) invoke(service, "classify", new IOException("bad")))
                .isEqualTo(BitcodeReasonCode.INTERNAL_ERROR);
        assertThat((Boolean) invoke(service, "matches", (Object) null)).isFalse();
        StoredArtifactView noSummary = artifact(collaborators(true).request, "manifest", null);
        assertThat((Boolean) invoke(service, "matches", noSummary)).isFalse();
    }

    @Test
    void rejectsEveryProducerIdentityMismatchAndSupportsFailureWithoutLogContext() {
        BitcodeArtifactService service = service(1024, 4096);
        BitcodeManifest manifest = BitcodeTestFixtures.manifest(List.of(BitcodeTestFixtures.failed(
                "failed", "src/a.c")));
        for (BitcodeManifest.Producer producer : List.of(
                new BitcodeManifest.Producer("clang", "20", "21.1.8", "x86_64"),
                new BitcodeManifest.Producer("clang", "21.1.8", "20", "x86_64"))) {
            BitcodeManifest changed = new BitcodeManifest(manifest.kind(), manifest.schemaVersion(),
                    manifest.artifactSetId(), manifest.sourceIdentityDigest(), manifest.compileContext(), producer,
                    manifest.status(), manifest.counts(), manifest.records(), manifest.scopes(),
                    manifest.generatedAt(), manifest.semanticDigest());
            assertThatThrownBy(() -> invoke(service, "validateIdentity", collaborators(true).request, changed))
                    .isInstanceOf(BitcodeRuntimeException.class);
        }
        BitcodeManifest missingProducer = new BitcodeManifest(manifest.kind(), manifest.schemaVersion(),
                manifest.artifactSetId(), manifest.sourceIdentityDigest(), manifest.compileContext(), null,
                manifest.status(), manifest.counts(), manifest.records(), manifest.scopes(),
                manifest.generatedAt(), manifest.semanticDigest());
        assertThatThrownBy(() -> invoke(service, "validateIdentity", collaborators(true).request, missingProducer))
                .isInstanceOf(BitcodeRuntimeException.class);
        Collaborators c = collaborators(true);
        BitcodeGenerationRequest withoutContext = new BitcodeGenerationRequest(c.request.projectId(),
                c.request.taskId(), c.request.buildRunId(), c.request.sourceRevisionId(),
                c.request.remoteSourcePath(), c.request.target(), c.request.jumpHost(), null);
        BitcodeGenerationResult result = invoke(service, "failed", withoutContext,
                BitcodeReasonCode.INTERNAL_ERROR, "bad");
        assertThat(result.summary().status()).isEqualTo(BitcodeStatus.FAILED);
    }

    private Collaborators configuredGeneration(BitcodeManifest manifest, byte[] bc, int producerExit) throws Exception {
        Collaborators c = collaborators(true);
        when(c.toolchain.ensure(any())).thenReturn(toolchain());
        when(c.ssh.execute(any())).thenReturn(ok(),
                new SshCommandResult(producerExit, "", "", Duration.ZERO), ok());
        Path manifestPath = writeManifest(manifest);
        Path bundle = writeBundle("source.tgz", required(manifest, bc, Files.readAllBytes(manifestPath)));
        org.mockito.Mockito.doAnswer(invocation -> {
            cn.rvport.backend.environment.runtime.SshFileTransferRequest request = invocation.getArgument(0);
            Files.copy(request.remotePath().endsWith("manifest.json") ? manifestPath : bundle,
                    request.localPath(), java.nio.file.StandardCopyOption.REPLACE_EXISTING);
            return null;
        }).when(c.ssh).download(any());
        return c;
    }

    private List<Entry> required(BitcodeManifest manifest, byte[] bc, byte[] manifestBytes) throws Exception {
        java.util.ArrayList<Entry> entries = new java.util.ArrayList<>();
        entries.add(entry("manifest.json", manifestBytes));
        for (BitcodeManifest.ArtifactRecord record : manifest.records()) {
            entries.add(entry("records/" + record.recordId() + ".json", mapper.writeValueAsBytes(record)));
            if (record.bitcode() != null) {
                entries.add(entry(record.bitcode().path(), bc));
            }
        }
        for (BitcodeManifest.Scope scope : manifest.scopes()) {
            entries.add(entry("scopes/" + scope.scopeId() + ".json", mapper.writeValueAsBytes(scope)));
        }
        return entries;
    }

    private Collaborators collaborators(boolean enabled) {
        RemoteBitcodeToolchainManager toolchain = mock(RemoteBitcodeToolchainManager.class);
        SshClientAdapter ssh = mock(SshClientAdapter.class);
        StoredArtifactService storage = mock(StoredArtifactService.class);
        TaskExecutionContext context = mock(TaskExecutionContext.class);
        SshConnectionTarget target = new SshConnectionTarget(UUID.randomUUID(), "host", 22, "root", "/work",
                new SshRuntimeCredential(CredentialKind.SSH_PASSWORD, "root", "password", null, null));
        BitcodeGenerationRequest request = new BitcodeGenerationRequest(UUID.randomUUID(), UUID.randomUUID(),
                UUID.randomUUID(), UUID.randomUUID(), "/work/source", target, null, context);
        return new Collaborators(service(enabled, toolchain, ssh, storage), toolchain, ssh, storage, request);
    }

    private BitcodeArtifactService service(long maxTuBytes, long maxBundleBytes) {
        return service(true, mock(RemoteBitcodeToolchainManager.class), mock(SshClientAdapter.class),
                mock(StoredArtifactService.class), maxTuBytes, maxBundleBytes);
    }

    private BitcodeArtifactService service(boolean enabled, RemoteBitcodeToolchainManager toolchain,
                                           SshClientAdapter ssh, StoredArtifactService storage) {
        return service(enabled, toolchain, ssh, storage, 1024 * 1024, 10 * 1024 * 1024);
    }

    private BitcodeArtifactService service(boolean enabled, RemoteBitcodeToolchainManager toolchain,
                                           SshClientAdapter ssh, StoredArtifactService storage,
                                           long maxTuBytes, long maxBundleBytes) {
        RvPortProperties.Bitcode props = new RvPortProperties.Bitcode(enabled, "llvm-test", "21.1.8",
                "bundle", "a".repeat(64), ".rvport/toolchains", 10, maxTuBytes, maxBundleBytes,
                10, 60, 60);
        return new BitcodeArtifactService(toolchain, ssh, storage, mapper,
                new RvPortProperties(null, null, null, props));
    }

    private RemoteBitcodeToolchain toolchain() {
        return new RemoteBitcodeToolchain("/toolchain", "/toolchain/bin/clang", "/toolchain/bin/clang++",
                "/toolchain/bin/llvm-dis", "llvm-test", "21.1.8");
    }

    private SshCommandResult ok() {
        return new SshCommandResult(0, "", "", Duration.ZERO);
    }

    private Map<String, Object> summary(int planned, int produced, int failed, int missing) {
        return Map.ofEntries(
                Map.entry("schemaVersion", BitcodeManifest.SCHEMA_VERSION),
                Map.entry("artifactSetId", BitcodeTestFixtures.HASH_A),
                Map.entry("sourceIdentityDigest", BitcodeTestFixtures.HASH_B),
                Map.entry("compileContextDigest", BitcodeTestFixtures.HASH_A),
                Map.entry("bundleSha256", BitcodeTestFixtures.HASH_B),
                Map.entry("toolchainId", "llvm-test"), Map.entry("toolchainVersion", "21.1.8"),
                Map.entry("plannedCount", planned), Map.entry("succeededCount", produced),
                Map.entry("failedCount", failed), Map.entry("skippedCount", missing), Map.entry("totalBytes", 20L));
    }

    private StoredArtifactView artifact(BitcodeGenerationRequest request, String type, Map<String, Object> summary) {
        return new StoredArtifactView(UUID.randomUUID(), request.projectId(), request.taskId(),
                StoredArtifactOwnerType.BUILD_VALIDATION, request.buildRunId(), type, "bucket", "object",
                "application/octet-stream", 10, BitcodeTestFixtures.HASH_A, summary, OffsetDateTime.now());
    }

    private Path writeManifest(BitcodeManifest manifest) throws Exception {
        Path path = tempDir.resolve(UUID.randomUUID() + ".json");
        mapper.writeValue(path.toFile(), manifest);
        return path;
    }

    private Path writeBundle(String name, List<Entry> entries) throws Exception {
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        try (GzipCompressorOutputStream gzip = new GzipCompressorOutputStream(output);
             TarArchiveOutputStream tar = new TarArchiveOutputStream(gzip)) {
            for (Entry data : entries) {
                TarArchiveEntry entry = data.entry();
                if (entry.isFile()) {
                    entry.setSize(data.content().length);
                }
                tar.putArchiveEntry(entry);
                if (entry.isFile()) {
                    tar.write(data.content());
                }
                tar.closeArchiveEntry();
            }
        }
        Path path = tempDir.resolve(name);
        Files.write(path, output.toByteArray());
        return path;
    }

    private Entry entry(String name, byte[] content) {
        return new Entry(new TarArchiveEntry(name), content);
    }

    private Entry link(String name, String target) {
        TarArchiveEntry entry = new TarArchiveEntry(name, TarArchiveEntry.LF_SYMLINK);
        entry.setLinkName(target);
        return new Entry(entry, new byte[0]);
    }

    private String sha(byte[] content) throws Exception {
        return java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(content));
    }

    @SuppressWarnings("unchecked")
    private <T> T invoke(Object target, String method, Object... arguments) {
        return (T) ReflectionTestUtils.invokeMethod(target, method, arguments);
    }

    private record Entry(TarArchiveEntry entry, byte[] content) {
    }

    private record Collaborators(BitcodeArtifactService service, RemoteBitcodeToolchainManager toolchain,
                                 SshClientAdapter ssh, StoredArtifactService storage,
                                 BitcodeGenerationRequest request) {
    }
}
