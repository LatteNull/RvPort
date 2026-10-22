package cn.rvport.backend.useraction;

import static org.assertj.core.api.Assertions.assertThatNoException;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.config.UserActionTokenCleanupProperties;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class UserActionTokenCleanupSchedulerTests {

    @Mock
    private UserActionTokenCleanupService cleanupService;

    @Test
    void skipsCleanupWhenDisabled() {
        UserActionTokenCleanupScheduler scheduler = new UserActionTokenCleanupScheduler(
                cleanupService,
                properties(false, 30));

        scheduler.cleanup();

        verify(cleanupService, never()).cleanup(30);
    }

    @Test
    void runsCleanupWithConfiguredRetentionDays() {
        UserActionTokenCleanupScheduler scheduler = new UserActionTokenCleanupScheduler(
                cleanupService,
                properties(true, 45));

        scheduler.cleanup();

        verify(cleanupService).cleanup(45);
    }

    @Test
    void catchesCleanupFailureSoAuthenticationFlowIsNotAffected() {
        UserActionTokenCleanupScheduler scheduler = new UserActionTokenCleanupScheduler(
                cleanupService,
                properties(true, 30));
        when(cleanupService.cleanup(30)).thenThrow(new IllegalStateException("database unavailable"));

        assertThatNoException().isThrownBy(scheduler::cleanup);

        verify(cleanupService).cleanup(30);
    }

    private static UserActionTokenCleanupProperties properties(boolean enabled, int retentionDays) {
        return new UserActionTokenCleanupProperties(enabled, "0 0 3 * * *", retentionDays);
    }
}
