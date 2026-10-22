package cn.rvport.backend.artifact;

public record ObjectStoragePutResult(
        String bucket,
        String objectKey,
        String contentType,
        long sizeBytes
) {
}
