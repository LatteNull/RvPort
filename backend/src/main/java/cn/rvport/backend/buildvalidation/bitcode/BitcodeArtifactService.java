package cn.rvport.backend.buildvalidation.bitcode;

import cn.rvport.backend.artifact.StoredArtifactCreateCommand;
import cn.rvport.backend.artifact.StoredArtifactOwnerType;
import cn.rvport.backend.artifact.StoredArtifactService;
import cn.rvport.backend.artifact.StoredArtifactView;
import cn.rvport.backend.buildvalidation.BuildValidationArtifacts;
import cn.rvport.backend.config.RvPortProperties;
import cn.rvport.backend.environment.runtime.SshClientAdapter;
import cn.rvport.backend.environment.runtime.SshCommandRequest;
import cn.rvport.backend.environment.runtime.SshCommandResult;
import cn.rvport.backend.environment.runtime.SshFileTransferRequest;
import cn.rvport.backend.task.TaskLogType;
import cn.rvport.backend.worker.TaskCancelledException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.JsonNode;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.time.Duration;
import java.util.HashMap;
import java.util.HashSet;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.locks.ReentrantLock;
import org.apache.commons.compress.archivers.tar.TarArchiveEntry;
import org.apache.commons.compress.archivers.tar.TarArchiveInputStream;
import org.apache.commons.compress.compressors.gzip.GzipCompressorInputStream;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;

@Service
public class BitcodeArtifactService {

    private static final long MAX_MANIFEST_BYTES = 16L * 1024L * 1024L;
    private static final ConcurrentHashMap<UUID, ReentrantLock> GENERATION_LOCKS = new ConcurrentHashMap<>();
    private final RemoteBitcodeToolchainManager toolchainManager;
    private final SshClientAdapter sshClientAdapter;
    private final StoredArtifactService storedArtifactService;
    private final ObjectMapper objectMapper;
    private final RvPortProperties.Bitcode properties;

    public BitcodeArtifactService(
            RemoteBitcodeToolchainManager toolchainManager,
            SshClientAdapter sshClientAdapter,
            StoredArtifactService storedArtifactService,
            ObjectMapper objectMapper,
            RvPortProperties properties
    ) {
        this.toolchainManager = toolchainManager;
        this.sshClientAdapter = sshClientAdapter;
        this.storedArtifactService = storedArtifactService;
        this.objectMapper = objectMapper;
        this.properties = properties.bitcode();
    }

    public BitcodeGenerationResult generate(BitcodeGenerationRequest request) {
        if (!properties.enabled()) {
            return BitcodeGenerationResult.unavailable(BitcodeStatus.NOT_ATTEMPTED, BitcodeReasonCode.DISABLED);
        }
        ReentrantLock lock = GENERATION_LOCKS.computeIfAbsent(request.buildRunId(), ignored -> new ReentrantLock());
        lock.lock();
        try {
            BitcodeGenerationResult reused = reusable(request);
            return reused == null ? generateFresh(request) : reused;
        } finally {
            lock.unlock();
            if (!lock.hasQueuedThreads()) {
                GENERATION_LOCKS.remove(request.buildRunId(), lock);
            }
        }
    }

    private BitcodeGenerationResult generateFresh(BitcodeGenerationRequest request) {
        Path localTemp = null;
        String remoteTemp = joinRemote(request.remoteSourcePath(), ".rvport-bitcode-" + request.taskId());
        try {
            request.executionContext().progress(80, "正在准备远端 LLVM Bitcode 工具链");
            RemoteBitcodeToolchain toolchain = toolchainManager.ensure(request);
            localTemp = Files.createTempDirectory("rvport-bitcode-");
            prepareProducer(request, remoteTemp);
            request.executionContext().progress(84, "正在远端生成 LLVM Bitcode 副产物");
            SshCommandResult produced = executeProducer(request, toolchain, remoteTemp);
            if (produced.exitCode() != 0) {
                return failed(request, BitcodeReasonCode.TRANSLATION_UNIT_FAILED,
                        "远端 LLVM Bitcode 生产器执行失败");
            }
            Path manifestFile = localTemp.resolve("manifest.json");
            Path bundleFile = localTemp.resolve("bitcode-bundle.tgz");
            request.executionContext().progress(87, "正在回收并校验 LLVM Bitcode 制品");
            download(request, remoteTemp + "/manifest.json", manifestFile, MAX_MANIFEST_BYTES);
            download(request, remoteTemp + "/bitcode-bundle.tgz", bundleFile, properties.maxBundleBytes());
            BitcodeManifest manifest = objectMapper.readValue(manifestFile.toFile(), BitcodeManifest.class);
            validateIdentity(request, manifest);
            if (manifest.counts() != null && manifest.counts().plannedRecords() == 0) {
                return BitcodeGenerationResult.unavailable(
                        BitcodeStatus.UNSUPPORTED, BitcodeReasonCode.NO_C_CPP_TRANSLATION_UNITS);
            }
            BitcodeManifestValidator.validate(manifest, properties.maxTranslationUnits(), properties.maxBundleBytes());
            validateBundle(manifest, manifestFile, bundleFile);
            return store(request, manifest, manifestFile, bundleFile);
        } catch (cn.rvport.backend.worker.TaskAttemptLostException ex) {
            throw ex;
        } catch (TaskCancelledException ex) {
            throw ex;
        } catch (BitcodeRuntimeException ex) {
            return failed(request, ex.reasonCode(), ex.getMessage());
        } catch (Exception ex) {
            String detail = ex.getMessage() == null || ex.getMessage().isBlank()
                    ? ex.getClass().getSimpleName()
                    : ex.getClass().getSimpleName() + ": " + ex.getMessage();
            return failed(request, classify(ex), "LLVM Bitcode 副产物生成失败: " + detail);
        } finally {
            cleanupRemote(request, remoteTemp);
            cleanupLocal(localTemp);
        }
    }

    private BitcodeGenerationResult reusable(BitcodeGenerationRequest request) {
        StoredArtifactView manifest = storedArtifactService.findByOwner(
                StoredArtifactOwnerType.BUILD_VALIDATION, request.buildRunId(),
                BuildValidationArtifacts.LLVM_BITCODE_MANIFEST_JSON).orElse(null);
        StoredArtifactView bundle = storedArtifactService.findByOwner(
                StoredArtifactOwnerType.BUILD_VALIDATION, request.buildRunId(),
                BuildValidationArtifacts.LLVM_BITCODE_BUNDLE_TGZ).orElse(null);
        if (!matches(manifest) || !matches(bundle)
                || !storedArtifactService.objectExists(manifest) || !storedArtifactService.objectExists(bundle)) {
            return null;
        }
        Map<String, Object> values = manifest.summary();
        int planned = number(values, "plannedCount");
        int succeeded = number(values, "succeededCount");
        int failed = number(values, "failedCount");
        int skipped = number(values, "skippedCount");
        String artifactSetId = string(values, "artifactSetId");
        BitcodeStatus status = succeeded == planned && planned > 0
                ? BitcodeStatus.READY : succeeded > 0 ? BitcodeStatus.PARTIAL : BitcodeStatus.FAILED;
        return new BitcodeGenerationResult(new BitcodeSummary(
                status == BitcodeStatus.READY || status == BitcodeStatus.PARTIAL,
                status,
                status == BitcodeStatus.READY ? BitcodeReasonCode.NONE : BitcodeReasonCode.TRANSLATION_UNIT_FAILED,
                BitcodeManifest.SCHEMA_VERSION,
                false,
                artifactSetId,
                string(values, "sourceIdentityDigest"),
                string(values, "compileContextDigest"),
                string(values, "bundleSha256"),
                properties.toolchainId(),
                properties.toolchainVersion(),
                planned,
                succeeded,
                failed,
                skipped,
                failed + skipped,
                longNumber(values, "totalBytes"),
                manifest.id(),
                bundle.id()
        ), List.of(manifest, bundle));
    }

    private boolean matches(StoredArtifactView artifact) {
        return artifact != null && artifact.summary() != null
                && BitcodeManifest.SCHEMA_VERSION.equals(String.valueOf(artifact.summary().get("schemaVersion")))
                && properties.toolchainId().equals(String.valueOf(artifact.summary().get("toolchainId")))
                && properties.toolchainVersion().equals(String.valueOf(artifact.summary().get("toolchainVersion")));
    }

    private String string(Map<String, Object> values, String key) {
        Object value = values == null ? null : values.get(key);
        return value == null ? null : String.valueOf(value);
    }

    private int number(Map<String, Object> values, String key) {
        Object value = values == null ? null : values.get(key);
        return value instanceof Number number ? number.intValue() : 0;
    }

    private long longNumber(Map<String, Object> values, String key) {
        Object value = values == null ? null : values.get(key);
        return value instanceof Number number ? number.longValue() : 0L;
    }

    private void prepareProducer(BitcodeGenerationRequest request, String remoteTemp) throws IOException {
        String script = new ClassPathResource("bitcode/produce_bitcode.py")
                .getContentAsString(StandardCharsets.UTF_8);
        SshCommandResult result = sshClientAdapter.execute(new SshCommandRequest(
                request.target(), request.jumpHost(),
                "set -eu; rm -rf " + shellQuote(remoteTemp) + "; mkdir -p " + shellQuote(remoteTemp)
                        + "; cat > " + shellQuote(remoteTemp + "/produce_bitcode.py")
                        + "; chmod 700 " + shellQuote(remoteTemp + "/produce_bitcode.py"),
                script, false, Duration.ofSeconds(30), Duration.ofSeconds(60), request.executionContext()
        ));
        if (result.exitCode() != 0) {
            throw new BitcodeRuntimeException(BitcodeReasonCode.TRANSFER_FAILED,
                    "远端 LLVM Bitcode 生产器准备失败");
        }
    }

    private SshCommandResult executeProducer(
            BitcodeGenerationRequest request,
            RemoteBitcodeToolchain toolchain,
            String remoteTemp
    ) {
        String command = "python3 " + shellQuote(remoteTemp + "/produce_bitcode.py")
                + " --compile-db " + shellQuote(joinRemote(request.remoteSourcePath(), "compile_commands.json"))
                + " --source-root " + shellQuote(request.remoteSourcePath())
                + " --output-dir " + shellQuote(remoteTemp + "/output")
                + " --clang " + shellQuote(toolchain.clang())
                + " --clangxx " + shellQuote(toolchain.clangxx())
                + " --llvm-dis " + shellQuote(toolchain.llvmDis())
                + " --manifest " + shellQuote(remoteTemp + "/manifest.json")
                + " --bundle " + shellQuote(remoteTemp + "/bitcode-bundle.tgz")
                + " --toolchain-id " + shellQuote(toolchain.toolchainId())
                + " --toolchain-version " + shellQuote(toolchain.version())
                + " --max-tu " + properties.maxTranslationUnits()
                + " --max-tu-bytes " + properties.maxTranslationUnitBytes()
                + " --max-total-bytes " + properties.maxBundleBytes()
                + " --tu-timeout " + properties.translationUnitTimeoutSeconds()
                + " --total-timeout " + properties.timeoutSeconds();
        return sshClientAdapter.execute(new SshCommandRequest(
                request.target(), request.jumpHost(), command, null, false,
                Duration.ofSeconds(30), Duration.ofSeconds(properties.timeoutSeconds() + 30L),
                request.executionContext()
        ));
    }

    private void download(BitcodeGenerationRequest request, String remote, Path local, long maxBytes) {
        sshClientAdapter.download(new SshFileTransferRequest(
                request.target(), request.jumpHost(), local, remote, maxBytes,
                Duration.ofSeconds(30), Duration.ofSeconds(properties.transferTimeoutSeconds()),
                request.executionContext()
        ));
    }

    private BitcodeGenerationResult store(
            BitcodeGenerationRequest request,
            BitcodeManifest manifest,
            Path manifestFile,
            Path bundleFile
    ) throws IOException {
        String bundleSha256 = sha256(bundleFile);
        Map<String, Object> artifactSummary = safeArtifactSummary(manifest, bundleSha256);
        StoredArtifactView manifestArtifact = storedArtifactService.store(new StoredArtifactCreateCommand(
                request.projectId(), request.taskId(), StoredArtifactOwnerType.BUILD_VALIDATION,
                request.buildRunId(), BuildValidationArtifacts.LLVM_BITCODE_MANIFEST_JSON,
                "application/json", Files.readAllBytes(manifestFile), artifactSummary, "json"
        ), request.executionContext());
        try {
            StoredArtifactView bundleArtifact = storedArtifactService.storeLargeFile(
                    request.projectId(), request.taskId(), StoredArtifactOwnerType.BUILD_VALIDATION,
                    request.buildRunId(), BuildValidationArtifacts.LLVM_BITCODE_BUNDLE_TGZ,
                    bundleFile, "application/gzip", artifactSummary, "tgz", request.executionContext()
            );
            BitcodeStatus status = manifest.counts().produced() == manifest.counts().plannedRecords()
                    && manifest.counts().plannedRecords() > 0
                    ? BitcodeStatus.READY
                    : manifest.counts().produced() > 0 ? BitcodeStatus.PARTIAL : BitcodeStatus.FAILED;
            BitcodeReasonCode reason = status == BitcodeStatus.READY
                    ? BitcodeReasonCode.NONE : BitcodeReasonCode.TRANSLATION_UNIT_FAILED;
            BitcodeSummary summary = new BitcodeSummary(
                    status == BitcodeStatus.READY || status == BitcodeStatus.PARTIAL,
                    status, reason, manifest.schemaVersion(), false, manifest.artifactSetId(),
                    manifest.sourceIdentityDigest(), manifest.compileContext().normalizedDigest(), bundleSha256,
                    properties.toolchainId(), properties.toolchainVersion(), manifest.counts().plannedRecords(),
                    manifest.counts().produced(), manifest.counts().failed(), manifest.counts().missing(),
                    manifest.counts().failed() + manifest.counts().missing(), manifest.counts().totalBytes(),
                    manifestArtifact.id(), bundleArtifact.id()
            );
            return new BitcodeGenerationResult(summary, List.of(manifestArtifact, bundleArtifact));
        } catch (cn.rvport.backend.worker.TaskAttemptLostException ex) {
            throw ex;
        } catch (Exception ex) {
            storedArtifactService.delete(manifestArtifact, request.executionContext());
            throw ex;
        }
    }

    private void validateIdentity(BitcodeGenerationRequest request, BitcodeManifest manifest) {
        if (manifest.producer() == null
                || !properties.toolchainVersion().equals(manifest.producer().version())
                || !properties.toolchainVersion().equals(manifest.producer().llvmVersion())) {
            throw new BitcodeRuntimeException(BitcodeReasonCode.MANIFEST_INVALID,
                    "LLVM Bitcode manifest 身份不匹配");
        }
    }

    private void validateBundle(BitcodeManifest manifest, Path manifestFile, Path bundleFile) throws IOException {
        BitcodeBundleValidator.validate(manifest, manifestFile, bundleFile, objectMapper,
                properties.maxTranslationUnits(), properties.maxBundleBytes(), properties.maxTranslationUnitBytes());
    }

    private Map<String, Object> safeArtifactSummary(BitcodeManifest manifest, String bundleSha256) {
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("schemaVersion", manifest.schemaVersion());
        summary.put("legacy", false);
        summary.put("artifactSetId", manifest.artifactSetId());
        summary.put("sourceIdentityDigest", manifest.sourceIdentityDigest());
        summary.put("compileContextDigest", manifest.compileContext().normalizedDigest());
        summary.put("bundleSha256", bundleSha256);
        summary.put("toolchainId", properties.toolchainId());
        summary.put("toolchainVersion", properties.toolchainVersion());
        summary.put("plannedCount", manifest.counts().plannedRecords());
        summary.put("succeededCount", manifest.counts().produced());
        summary.put("failedCount", manifest.counts().failed());
        summary.put("skippedCount", manifest.counts().missing());
        summary.put("totalBytes", manifest.counts().totalBytes());
        return summary;
    }

    private BitcodeGenerationResult failed(
            BitcodeGenerationRequest request,
            BitcodeReasonCode reason,
            String message
    ) {
        if (request.executionContext() != null) {
            request.executionContext().log(TaskLogType.STDERR,
                    "RVPORT_OBSERVATION_WARNING llvmBitcodeUnavailable reason=" + reason.name()
                            + " message=" + safeMessage(message) + System.lineSeparator());
        }
        return BitcodeGenerationResult.unavailable(BitcodeStatus.FAILED, reason);
    }

    private BitcodeReasonCode classify(Exception ex) {
        if (ex instanceof com.fasterxml.jackson.core.JsonProcessingException || ex instanceof IllegalArgumentException) {
            return BitcodeReasonCode.MANIFEST_INVALID;
        }
        if (ex instanceof cn.rvport.backend.artifact.ObjectStorageException) {
            return BitcodeReasonCode.STORAGE_FAILED;
        }
        if (ex instanceof cn.rvport.backend.environment.runtime.SshRuntimeException) {
            return BitcodeReasonCode.TRANSFER_FAILED;
        }
        return BitcodeReasonCode.INTERNAL_ERROR;
    }

    private void cleanupRemote(BitcodeGenerationRequest request, String remoteTemp) {
        try {
            sshClientAdapter.execute(new SshCommandRequest(
                    request.target(), request.jumpHost(), "rm -rf " + shellQuote(remoteTemp),
                    Duration.ofSeconds(30), Duration.ofSeconds(60)
            ));
        } catch (Exception ignored) {
            // 远端工作目录中的 task-scoped 临时目录会在后续同任务重试时再次清理。
        }
    }

    private void cleanupLocal(Path directory) {
        if (directory == null) {
            return;
        }
        try (var paths = Files.walk(directory)) {
            paths.sorted(java.util.Comparator.reverseOrder()).forEach(path -> {
                try {
                    Files.deleteIfExists(path);
                } catch (IOException ignored) {
                    // JVM 临时目录清理由操作系统兜底。
                }
            });
        } catch (IOException ignored) {
            // JVM 临时目录清理由操作系统兜底。
        }
    }

    private String sha256(Path path) throws IOException {
        MessageDigest digest = sha256Digest();
        try (InputStream input = Files.newInputStream(path)) {
            byte[] buffer = new byte[64 * 1024];
            int read;
            while ((read = input.read(buffer)) >= 0) {
                if (read > 0) {
                    digest.update(buffer, 0, read);
                }
            }
        }
        return HexFormat.of().formatHex(digest.digest());
    }

    private MessageDigest sha256Digest() {
        try {
            return MessageDigest.getInstance("SHA-256");
        } catch (java.security.NoSuchAlgorithmException ex) {
            throw new IllegalStateException(ex);
        }
    }

    private String joinRemote(String base, String child) {
        return base.replaceAll("/+$", "") + "/" + child.replaceAll("^/+", "");
    }

    private String shellQuote(String value) {
        return "'" + value.replace("'", "'\"'\"'") + "'";
    }

    private String safeMessage(String value) {
        return value == null ? "" : value.replace('\r', ' ').replace('\n', ' ').replaceAll("[/\\\\][^ ]+", "<PATH>");
    }
}
