package cn.rvport.backend.artifact;

import cn.rvport.backend.config.ObjectStorageProperties;
import java.net.URI;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.atomic.AtomicBoolean;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import software.amazon.awssdk.auth.credentials.AwsBasicCredentials;
import software.amazon.awssdk.auth.credentials.StaticCredentialsProvider;
import software.amazon.awssdk.core.ResponseBytes;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.http.urlconnection.UrlConnectionHttpClient;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.CreateBucketRequest;
import software.amazon.awssdk.services.s3.model.DeleteObjectRequest;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;
import software.amazon.awssdk.services.s3.model.GetObjectResponse;
import software.amazon.awssdk.services.s3.model.HeadBucketRequest;
import software.amazon.awssdk.services.s3.model.HeadObjectRequest;
import software.amazon.awssdk.services.s3.model.NoSuchBucketException;
import software.amazon.awssdk.services.s3.model.NoSuchKeyException;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;
import software.amazon.awssdk.services.s3.model.S3Exception;

@Service
public class S3ObjectStorageService implements ObjectStorageService {

    private final ObjectStorageProperties properties;
    private final S3Client s3Client;
    private final AtomicBoolean bucketChecked = new AtomicBoolean(false);

    @Autowired
    public S3ObjectStorageService(ObjectStorageProperties properties) {
        this(properties, S3Client.builder()
                .endpointOverride(URI.create(properties.endpoint()))
                .region(Region.of(properties.region()))
                .credentialsProvider(StaticCredentialsProvider.create(
                        AwsBasicCredentials.create(properties.accessKey(), properties.secretKey())))
                .forcePathStyle(properties.pathStyle())
                .httpClientBuilder(UrlConnectionHttpClient.builder())
                .build());
    }

    S3ObjectStorageService(ObjectStorageProperties properties, S3Client s3Client) {
        this.properties = properties;
        this.s3Client = s3Client;
    }

    @Override
    public ObjectStoragePutResult put(String objectKey, String contentType, byte[] content) {
        ensureEnabled();
        ensureBucket();
        try {
            s3Client.putObject(PutObjectRequest.builder()
                            .bucket(properties.bucket())
                            .key(objectKey)
                            .contentType(contentType)
                            .contentLength((long) content.length)
                            .build(),
                    RequestBody.fromBytes(content));
            return new ObjectStoragePutResult(properties.bucket(), objectKey, contentType, content.length);
        } catch (RuntimeException ex) {
            throw storageError("对象存储写入失败", ex);
        }
    }

    @Override
    public ObjectStoragePutResult putFile(String objectKey, String contentType, Path file) {
        ensureEnabled();
        ensureBucket();
        try {
            long size = Files.size(file);
            s3Client.putObject(PutObjectRequest.builder()
                            .bucket(properties.bucket())
                            .key(objectKey)
                            .contentType(contentType)
                            .contentLength(size)
                            .build(),
                    RequestBody.fromFile(file));
            return new ObjectStoragePutResult(properties.bucket(), objectKey, contentType, size);
        } catch (java.io.IOException | RuntimeException ex) {
            throw new ObjectStorageException("对象存储文件写入失败", ex);
        }
    }

    @Override
    public ObjectStorageObject get(String bucket, String objectKey) {
        ensureEnabled();
        try {
            ResponseBytes<GetObjectResponse> response = s3Client.getObjectAsBytes(GetObjectRequest.builder()
                    .bucket(bucket)
                    .key(objectKey)
                    .build());
            String contentType = response.response().contentType();
            return new ObjectStorageObject(
                    bucket,
                    objectKey,
                    contentType == null || contentType.isBlank() ? "application/octet-stream" : contentType,
                    response.asByteArray().length,
                    response.asByteArray()
            );
        } catch (NoSuchBucketException | NoSuchKeyException ex) {
            throw new ObjectStorageException("对象存储文件不存在", ex);
        } catch (RuntimeException ex) {
            throw storageError("对象存储读取失败", ex);
        }
    }

    @Override
    public boolean exists(String bucket, String objectKey) {
        ensureEnabled();
        try {
            s3Client.headObject(HeadObjectRequest.builder().bucket(bucket).key(objectKey).build());
            return true;
        } catch (NoSuchBucketException | NoSuchKeyException ex) {
            return false;
        } catch (S3Exception ex) {
            if (ex.statusCode() == 404) {
                return false;
            }
            throw storageError("对象存储状态检查失败", ex);
        }
    }

    @Override
    public void delete(String bucket, String objectKey) {
        if (!properties.enabled() || bucket == null || bucket.isBlank() || objectKey == null || objectKey.isBlank()) {
            return;
        }
        try {
            s3Client.deleteObject(DeleteObjectRequest.builder().bucket(bucket).key(objectKey).build());
        } catch (RuntimeException ex) {
            throw storageError("对象存储删除失败", ex);
        }
    }

    private void ensureBucket() {
        if (bucketChecked.get()) {
            return;
        }
        try {
            s3Client.headBucket(HeadBucketRequest.builder().bucket(properties.bucket()).build());
            bucketChecked.set(true);
        } catch (NoSuchBucketException ex) {
            createBucket();
        } catch (S3Exception ex) {
            if (ex.statusCode() == 404) {
                createBucket();
                return;
            }
            throw storageError("对象存储 bucket 检查失败", ex);
        }
    }

    private void createBucket() {
        if (!properties.autoCreateBucket()) {
            throw new ObjectStorageException("对象存储 bucket 不存在", null);
        }
        try {
            s3Client.createBucket(CreateBucketRequest.builder().bucket(properties.bucket()).build());
            bucketChecked.set(true);
        } catch (RuntimeException ex) {
            throw storageError("对象存储 bucket 创建失败", ex);
        }
    }

    private void ensureEnabled() {
        if (!properties.enabled()) {
            throw new ObjectStorageException("对象存储未启用", null);
        }
    }

    private ObjectStorageException storageError(String message, RuntimeException ex) {
        return new ObjectStorageException(message, ex);
    }
}
