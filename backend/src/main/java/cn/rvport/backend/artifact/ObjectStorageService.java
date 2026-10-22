package cn.rvport.backend.artifact;

import java.nio.file.Path;

public interface ObjectStorageService {

    ObjectStoragePutResult put(String objectKey, String contentType, byte[] content);

    ObjectStoragePutResult putFile(String objectKey, String contentType, Path file);

    ObjectStorageObject get(String bucket, String objectKey);

    boolean exists(String bucket, String objectKey);

    void delete(String bucket, String objectKey);
}
