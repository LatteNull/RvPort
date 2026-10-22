package cn.rvport.backend.buildvalidation.bitcode;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HashMap;
import java.util.HashSet;
import java.util.HexFormat;
import java.util.Map;
import java.util.Set;
import org.apache.commons.compress.archivers.tar.TarArchiveEntry;
import org.apache.commons.compress.archivers.tar.TarArchiveInputStream;
import org.apache.commons.compress.compressors.gzip.GzipCompressorInputStream;

public final class BitcodeBundleValidator {

    private BitcodeBundleValidator() {
    }

    public static void validate(
            BitcodeManifest manifest,
            Path manifestFile,
            Path bundleFile,
            ObjectMapper objectMapper,
            int maxRecords,
            long maxBundleBytes,
            long maxEntryBytes
    ) throws IOException {
        JsonNode rawManifest = objectMapper.valueToTree(manifest);
        validate(manifest, rawManifest, manifestFile, bundleFile, objectMapper,
                maxRecords, maxBundleBytes, maxEntryBytes);
    }

    public static void validate(
            BitcodeManifest manifest,
            JsonNode rawManifest,
            Path manifestFile,
            Path bundleFile,
            ObjectMapper objectMapper,
            int maxRecords,
            long maxBundleBytes,
            long maxEntryBytes
    ) throws IOException {
        try {
            BitcodeManifestValidator.validate(manifest, rawManifest, maxRecords, maxBundleBytes);
        } catch (IllegalArgumentException ex) {
            throw new BitcodeRuntimeException(new BitcodeVerificationFailure(
                    BitcodeVerificationStage.MANIFEST_SCHEMA,
                    BitcodeReasonCode.MANIFEST_SCHEMA_INVALID,
                    manifest == null ? null : manifest.schemaVersion(),
                    manifest == null || manifest.producer() == null ? null : manifest.producer().version(),
                    manifest == null ? null : manifest.artifactSetId(), null, null, false,
                    "LLVM Bitcode manifest 校验失败",
                    "LLVM Bitcode manifest validation failed.",
                    "检查 manifest 字段、计数和路径后重新生成制品。",
                    "Check manifest fields, counts, and paths, then regenerate the artifact."), ex);
        }
        if (Files.size(bundleFile) > maxBundleBytes) {
            throw invalid(BitcodeVerificationStage.MATERIALIZATION,
                    BitcodeReasonCode.OUTPUT_SIZE_LIMIT_EXCEEDED, "LLVM Bitcode bundle 超出大小预算");
        }
        Map<String, BitcodeManifest.Bitcode> expected = new HashMap<>();
        Map<String, JsonNode> expectedDocuments = new HashMap<>();
        Set<String> declaredEntries = new HashSet<>();
        for (int index = 0; index < manifest.records().size(); index++) {
            BitcodeManifest.ArtifactRecord record = manifest.records().get(index);
            String recordPath = "records/" + record.recordId() + ".json";
            declaredEntries.add(recordPath);
            expectedDocuments.put(recordPath, rawManifest.path("records").path(index));
            if (record.bitcode() != null) {
                expected.put(record.bitcode().path(), record.bitcode());
                declaredEntries.add(record.bitcode().path());
            }
            for (BitcodeManifest.Sidecar sidecar : record.sidecars()) {
                expected.put(sidecar.path(), new BitcodeManifest.Bitcode(
                        sidecar.path(), sidecar.bytes(), sidecar.sha256()));
                declaredEntries.add(sidecar.path());
            }
        }
        for (int index = 0; index < manifest.scopes().size(); index++) {
            BitcodeManifest.Scope scope = manifest.scopes().get(index);
            String scopePath = "scopes/" + scope.scopeId() + ".json";
            declaredEntries.add(scopePath);
            expectedDocuments.put(scopePath, rawManifest.path("scopes").path(index));
        }

        Set<String> observed = new HashSet<>();
        String expectedManifestSha = sha256(manifestFile);
        boolean manifestObserved = false;
        long extractedBytes = 0;
        int entries = 0;
        try (InputStream file = Files.newInputStream(bundleFile);
             GzipCompressorInputStream gzip = new GzipCompressorInputStream(file);
             TarArchiveInputStream tar = new TarArchiveInputStream(gzip)) {
            TarArchiveEntry entry;
            byte[] buffer = new byte[64 * 1024];
            while ((entry = tar.getNextTarEntry()) != null) {
                entries++;
                int maximumEntries = maxRecords * 4 + manifest.scopes().size() + 1;
                if (entries > maximumEntries || !entry.isFile() || entry.isSymbolicLink() || entry.isLink()) {
                    throw invalid(BitcodeVerificationStage.BUNDLE_LAYOUT,
                            BitcodeReasonCode.BUNDLE_LAYOUT_INVALID, "LLVM Bitcode bundle 包含非法条目");
                }
                try {
                    BitcodeManifestValidator.validateSafeRelativePath(entry.getName(), "bundleEntry");
                } catch (IllegalArgumentException ex) {
                    throw invalid(BitcodeVerificationStage.BUNDLE_LAYOUT,
                            BitcodeReasonCode.BUNDLE_LAYOUT_INVALID,
                            "LLVM Bitcode bundle 包含不安全路径", ex);
                }
                if (!observed.add(entry.getName())) {
                    throw invalid(BitcodeVerificationStage.BUNDLE_LAYOUT,
                            BitcodeReasonCode.BUNDLE_LAYOUT_INVALID, "LLVM Bitcode bundle 包含重复条目");
                }
                MessageDigest digest = sha256Digest();
                ByteArrayOutputStream documentBytes = expectedDocuments.containsKey(entry.getName())
                        ? new ByteArrayOutputStream() : null;
                long entryBytes = 0;
                int read;
                while ((read = tar.read(buffer)) >= 0) {
                    if (read == 0) {
                        continue;
                    }
                    entryBytes = Math.addExact(entryBytes, read);
                    extractedBytes = Math.addExact(extractedBytes, read);
                    if ((entryBytes > maxEntryBytes && !"manifest.json".equals(entry.getName()))
                            || extractedBytes > maxBundleBytes) {
                        throw invalid(BitcodeVerificationStage.MATERIALIZATION,
                                BitcodeReasonCode.OUTPUT_SIZE_LIMIT_EXCEEDED,
                                "LLVM Bitcode bundle 解包预算超限");
                    }
                    digest.update(buffer, 0, read);
                    if (documentBytes != null) {
                        documentBytes.write(buffer, 0, read);
                    }
                }
                String hash = HexFormat.of().formatHex(digest.digest());
                if ("manifest.json".equals(entry.getName())) {
                    manifestObserved = hash.equals(expectedManifestSha);
                    continue;
                }
                if (!declaredEntries.contains(entry.getName())) {
                    throw invalid(BitcodeVerificationStage.BUNDLE_LAYOUT,
                            BitcodeReasonCode.BUNDLE_LAYOUT_INVALID, "LLVM Bitcode bundle 包含未声明条目");
                }
                BitcodeManifest.Bitcode artifact = expected.get(entry.getName());
                if (artifact != null && (artifact.bytes() != entryBytes || !artifact.sha256().equals(hash))) {
                    throw invalid(BitcodeVerificationStage.MEMBER_INTEGRITY,
                            BitcodeReasonCode.MEMBER_INTEGRITY_MISMATCH,
                            "LLVM Bitcode bundle 条目与 manifest 不一致");
                }
                if (documentBytes != null) {
                    JsonNode actual = objectMapper.readTree(documentBytes.toByteArray());
                    String expectedDocumentDigest = BitcodeCanonicalIdentity.digest(
                            expectedDocuments.get(entry.getName()));
                    String actualDocumentDigest = BitcodeCanonicalIdentity.digest(actual);
                    if (!expectedDocumentDigest.equals(actualDocumentDigest)) {
                        String expectedDigest = expectedDocumentDigest.substring(0, 12);
                        String actualDigest = actualDocumentDigest.substring(0, 12);
                        throw invalid(BitcodeVerificationStage.MEMBER_INTEGRITY,
                                BitcodeReasonCode.MEMBER_INTEGRITY_MISMATCH,
                                "LLVM Bitcode bundle record/scope 与 manifest 不一致"
                                        + " expected=" + expectedDigest + " actual=" + actualDigest);
                    }
                }
            }
        }
        if (!manifestObserved || !observed.containsAll(declaredEntries)) {
            throw invalid(BitcodeVerificationStage.BUNDLE_LAYOUT,
                    BitcodeReasonCode.BUNDLE_LAYOUT_INVALID,
                    "LLVM Bitcode bundle 缺少 manifest 或 BC 条目");
        }
    }

    private static BitcodeRuntimeException invalid(BitcodeVerificationStage stage,
                                                   BitcodeReasonCode reason, String message) {
        return invalid(stage, reason, message, null);
    }

    private static BitcodeRuntimeException invalid(BitcodeVerificationStage stage,
                                                   BitcodeReasonCode reason, String message,
                                                   Throwable cause) {
        return new BitcodeRuntimeException(new BitcodeVerificationFailure(
                stage, reason, null, null, null, null, null, false,
                message, "LLVM Bitcode bundle validation failed.",
                "重新获取或重新生成共享 BC 制品。",
                "Fetch or regenerate the shared BC artifact."), cause);
    }

    private static String sha256(Path file) throws IOException {
        MessageDigest digest = sha256Digest();
        try (InputStream input = Files.newInputStream(file)) {
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

    private static MessageDigest sha256Digest() {
        try {
            return MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 不可用", ex);
        }
    }
}
