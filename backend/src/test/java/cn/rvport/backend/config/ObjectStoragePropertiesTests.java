package cn.rvport.backend.config;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class ObjectStoragePropertiesTests {

    @Test
    void preservesEndpointBucketCredentialsAndPathStyle() {
        ObjectStorageProperties properties = new ObjectStorageProperties(
                true,
                "http://localhost:9000",
                "us-east-1",
                "rvport-artifacts",
                "rvport",
                "secret",
                true,
                true
        );

        assertThat(properties.enabled()).isTrue();
        assertThat(properties.endpoint()).isEqualTo("http://localhost:9000");
        assertThat(properties.bucket()).isEqualTo("rvport-artifacts");
        assertThat(properties.pathStyle()).isTrue();
        assertThat(properties.autoCreateBucket()).isTrue();
    }
}
