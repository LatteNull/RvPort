package cn.rvport.backend.artifact;

public record ObjectStorageObject(
        String bucket,
        String objectKey,
        String contentType,
        long sizeBytes,
        byte[] content
) {
}
