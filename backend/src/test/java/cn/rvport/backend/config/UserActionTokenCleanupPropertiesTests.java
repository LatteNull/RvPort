package cn.rvport.backend.config;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class UserActionTokenCleanupPropertiesTests {

    @Test
    void normalizesDefaultsWhenCronOrRetentionAreInvalid() {
        UserActionTokenCleanupProperties properties = new UserActionTokenCleanupProperties(true, "", 0);

        assertThat(properties.enabled()).isTrue();
        assertThat(properties.cron()).isEqualTo("0 0 3 * * *");
        assertThat(properties.retentionDays()).isEqualTo(30);
    }
}
