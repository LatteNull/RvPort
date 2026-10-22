package cn.rvport.backend.analysis;

import cn.rvport.backend.buildvalidation.bitcode.BitcodeBundleValidator;
import cn.rvport.backend.buildvalidation.bitcode.BitcodeManifest;
import cn.rvport.backend.buildvalidation.bitcode.BitcodeManifestSchema;
import cn.rvport.backend.buildvalidation.bitcode.BitcodeReasonCode;
import cn.rvport.backend.buildvalidation.bitcode.BitcodeRuntimeException;
import cn.rvport.backend.buildvalidation.bitcode.BitcodeVerificationFailure;
import cn.rvport.backend.buildvalidation.bitcode.BitcodeVerificationStage;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.nio.file.Path;
import org.springframework.stereotype.Component;

@Component
public class SharedBitcodeArtifactVerifier {

    private final ObjectMapper objectMapper;

    public SharedBitcodeArtifactVerifier(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    public BitcodeManifest verify(
            Path manifestFile,
            Path bundleFile,
            int maxRecords,
            long maxBundleBytes,
            long maxEntryBytes
    ) throws IOException {
        try {
            JsonNode rawManifest = objectMapper.readTree(manifestFile.toFile());
            BitcodeManifestSchema.validateRaw(rawManifest);
            BitcodeManifest manifest = objectMapper.treeToValue(rawManifest, BitcodeManifest.class);
            BitcodeBundleValidator.validate(manifest, rawManifest, manifestFile, bundleFile, objectMapper,
                    maxRecords, maxBundleBytes, maxEntryBytes);
            return manifest;
        } catch (BitcodeRuntimeException ex) {
            throw ex;
        } catch (JsonProcessingException ex) {
            throw new BitcodeRuntimeException(new BitcodeVerificationFailure(
                    BitcodeVerificationStage.MANIFEST_PARSE,
                    BitcodeReasonCode.MANIFEST_PARSE_INVALID,
                    null, null, null, null, null, false,
                    "共享 BC manifest 无法解析。", "The shared BC manifest could not be parsed.",
                    "重新获取或重新生成 manifest。", "Fetch or regenerate the manifest."), ex);
        }
    }
}
