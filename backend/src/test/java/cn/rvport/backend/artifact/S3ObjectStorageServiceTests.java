package cn.rvport.backend.artifact;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.config.ObjectStorageProperties;
import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.Test;
import software.amazon.awssdk.core.ResponseBytes;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;
import software.amazon.awssdk.services.s3.model.GetObjectResponse;
import software.amazon.awssdk.services.s3.model.HeadBucketRequest;
import software.amazon.awssdk.services.s3.model.HeadObjectRequest;
import software.amazon.awssdk.services.s3.model.NoSuchBucketException;
import software.amazon.awssdk.services.s3.model.NoSuchKeyException;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;
import software.amazon.awssdk.services.s3.model.S3Exception;

class S3ObjectStorageServiceTests {

    @Test
    void publicConstructorBuildsClientWithoutOpeningAConnection() throws Exception {
        S3ObjectStorageService service = new S3ObjectStorageService(properties(false, true));
        service.delete("bucket", "key");

        var field = S3ObjectStorageService.class.getDeclaredField("s3Client");
        field.setAccessible(true);
        ((S3Client) field.get(service)).close();
    }

    @Test
    void disabledStorageRejectsReadsAndWritesAndSilentlySkipsDelete() {
        S3Client client = mock(S3Client.class);
        S3ObjectStorageService service = new S3ObjectStorageService(properties(false, true), client);

        assertThatThrownBy(() -> service.put("key", "text/plain", new byte[0]))
                .isInstanceOf(ObjectStorageException.class).hasMessageContaining("未启用");
        assertThatThrownBy(() -> service.get("bucket", "key"))
                .isInstanceOf(ObjectStorageException.class).hasMessageContaining("未启用");
        assertThatThrownBy(() -> service.exists("bucket", "key"))
                .isInstanceOf(ObjectStorageException.class).hasMessageContaining("未启用");
        service.delete("bucket", "key");
        verify(client, never()).deleteObject(any(software.amazon.awssdk.services.s3.model.DeleteObjectRequest.class));
    }

    @Test
    void putChecksBucketOnceAndReturnsStoredMetadata() {
        S3Client client = mock(S3Client.class);
        S3ObjectStorageService service = new S3ObjectStorageService(properties(true, true), client);
        byte[] content = "hello".getBytes(StandardCharsets.UTF_8);

        ObjectStoragePutResult first = service.put("a.txt", "text/plain", content);
        service.put("b.txt", "text/plain", content);

        assertThat(first.bucket()).isEqualTo("bucket");
        assertThat(first.objectKey()).isEqualTo("a.txt");
        assertThat(first.sizeBytes()).isEqualTo(content.length);
        verify(client).headBucket(any(HeadBucketRequest.class));
        verify(client, times(2)).putObject(any(PutObjectRequest.class), any(RequestBody.class));
    }

    @Test
    void missingBucketIsCreatedWhenAllowedAndRejectedOtherwise() {
        S3Client creatingClient = mock(S3Client.class);
        when(creatingClient.headBucket(any(HeadBucketRequest.class)))
                .thenThrow(NoSuchBucketException.builder().message("missing").build());
        S3ObjectStorageService creating = new S3ObjectStorageService(properties(true, true), creatingClient);

        creating.put("a", "text/plain", new byte[0]);
        verify(creatingClient).createBucket(any(software.amazon.awssdk.services.s3.model.CreateBucketRequest.class));

        S3Client rejectingClient = mock(S3Client.class);
        when(rejectingClient.headBucket(any(HeadBucketRequest.class)))
                .thenThrow(NoSuchBucketException.builder().message("missing").build());
        S3ObjectStorageService rejecting = new S3ObjectStorageService(properties(true, false), rejectingClient);
        assertThatThrownBy(() -> rejecting.put("a", "text/plain", new byte[0]))
                .isInstanceOf(ObjectStorageException.class).hasMessageContaining("bucket 不存在");
    }

    @Test
    void bucketStatusErrorsMap404ToCreationAndOtherFailuresToStorageError() {
        S3Client missing = mock(S3Client.class);
        S3Exception notFound = s3(404);
        when(missing.headBucket(any(HeadBucketRequest.class))).thenThrow(notFound);
        new S3ObjectStorageService(properties(true, true), missing).put("a", "text/plain", new byte[0]);
        verify(missing).createBucket(any(software.amazon.awssdk.services.s3.model.CreateBucketRequest.class));

        S3Client broken = mock(S3Client.class);
        S3Exception serverError = s3(500);
        when(broken.headBucket(any(HeadBucketRequest.class))).thenThrow(serverError);
        assertThatThrownBy(() -> new S3ObjectStorageService(properties(true, true), broken)
                .put("a", "text/plain", new byte[0]))
                .isInstanceOf(ObjectStorageException.class).hasMessageContaining("bucket 检查失败");
    }

    @Test
    void getPreservesContentTypeAndFallsBackWhenMissing() {
        S3Client client = mock(S3Client.class);
        byte[] content = "data".getBytes(StandardCharsets.UTF_8);
        when(client.getObjectAsBytes(any(GetObjectRequest.class)))
                .thenReturn(ResponseBytes.fromByteArray(GetObjectResponse.builder().contentType("text/plain").build(), content))
                .thenReturn(ResponseBytes.fromByteArray(GetObjectResponse.builder().contentType(" ").build(), content));
        S3ObjectStorageService service = new S3ObjectStorageService(properties(true, true), client);

        assertThat(service.get("other", "a").contentType()).isEqualTo("text/plain");
        ObjectStorageObject fallback = service.get("other", "b");
        assertThat(fallback.contentType()).isEqualTo("application/octet-stream");
        assertThat(fallback.content()).containsExactly(content);
        assertThat(fallback.sizeBytes()).isEqualTo(content.length);
    }

    @Test
    void getMapsMissingAndGenericFailures() {
        S3Client missing = mock(S3Client.class);
        when(missing.getObjectAsBytes(any(GetObjectRequest.class)))
                .thenThrow(NoSuchKeyException.builder().message("missing").build());
        assertThatThrownBy(() -> new S3ObjectStorageService(properties(true, true), missing).get("b", "k"))
                .isInstanceOf(ObjectStorageException.class).hasMessageContaining("不存在");

        S3Client broken = mock(S3Client.class);
        when(broken.getObjectAsBytes(any(GetObjectRequest.class))).thenThrow(new IllegalStateException("down"));
        assertThatThrownBy(() -> new S3ObjectStorageService(properties(true, true), broken).get("b", "k"))
                .isInstanceOf(ObjectStorageException.class).hasMessageContaining("读取失败");
    }

    @Test
    void existsHandlesPresentMissing404AndServerFailure() {
        S3Client present = mock(S3Client.class);
        assertThat(new S3ObjectStorageService(properties(true, true), present).exists("b", "k")).isTrue();

        S3Client missing = mock(S3Client.class);
        when(missing.headObject(any(HeadObjectRequest.class)))
                .thenThrow(NoSuchKeyException.builder().message("missing").build());
        assertThat(new S3ObjectStorageService(properties(true, true), missing).exists("b", "k")).isFalse();

        S3Client notFound = mock(S3Client.class);
        S3Exception missingError = s3(404);
        when(notFound.headObject(any(HeadObjectRequest.class))).thenThrow(missingError);
        assertThat(new S3ObjectStorageService(properties(true, true), notFound).exists("b", "k")).isFalse();

        S3Client broken = mock(S3Client.class);
        S3Exception unavailable = s3(503);
        when(broken.headObject(any(HeadObjectRequest.class))).thenThrow(unavailable);
        assertThatThrownBy(() -> new S3ObjectStorageService(properties(true, true), broken).exists("b", "k"))
                .isInstanceOf(ObjectStorageException.class).hasMessageContaining("状态检查失败");
    }

    @Test
    void deleteSkipsIncompleteKeysAndMapsClientFailure() {
        S3Client client = mock(S3Client.class);
        S3ObjectStorageService service = new S3ObjectStorageService(properties(true, true), client);
        service.delete(null, "key");
        service.delete(" ", "key");
        service.delete("bucket", null);
        service.delete("bucket", " ");
        verify(client, never()).deleteObject(any(software.amazon.awssdk.services.s3.model.DeleteObjectRequest.class));

        service.delete("bucket", "key");
        verify(client).deleteObject(any(software.amazon.awssdk.services.s3.model.DeleteObjectRequest.class));

        S3Client broken = mock(S3Client.class);
        doThrow(new IllegalStateException("down")).when(broken)
                .deleteObject(any(software.amazon.awssdk.services.s3.model.DeleteObjectRequest.class));
        assertThatThrownBy(() -> new S3ObjectStorageService(properties(true, true), broken).delete("b", "k"))
                .isInstanceOf(ObjectStorageException.class).hasMessageContaining("删除失败");
    }

    @Test
    void putAndCreateBucketFailuresAreMapped() {
        S3Client putBroken = mock(S3Client.class);
        when(putBroken.putObject(any(PutObjectRequest.class), any(RequestBody.class)))
                .thenThrow(new IllegalStateException("down"));
        assertThatThrownBy(() -> new S3ObjectStorageService(properties(true, true), putBroken)
                .put("a", "text/plain", new byte[0]))
                .isInstanceOf(ObjectStorageException.class).hasMessageContaining("写入失败");

        S3Client createBroken = mock(S3Client.class);
        when(createBroken.headBucket(any(HeadBucketRequest.class)))
                .thenThrow(NoSuchBucketException.builder().message("missing").build());
        when(createBroken.createBucket(any(software.amazon.awssdk.services.s3.model.CreateBucketRequest.class)))
                .thenThrow(new IllegalStateException("down"));
        assertThatThrownBy(() -> new S3ObjectStorageService(properties(true, true), createBroken)
                .put("a", "text/plain", new byte[0]))
                .isInstanceOf(ObjectStorageException.class).hasMessageContaining("bucket 创建失败");
    }

    private ObjectStorageProperties properties(boolean enabled, boolean autoCreate) {
        return new ObjectStorageProperties(enabled, "http://localhost:9000", "us-east-1", "bucket",
                "access", "secret", true, autoCreate);
    }

    private S3Exception s3(int status) {
        S3Exception failure = mock(S3Exception.class);
        when(failure.statusCode()).thenReturn(status);
        return failure;
    }
}
