package cn.rvport.backend.useraction;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.Clock;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class UserActionTokenCleanupServiceTests {

    @Mock
    private UserActionTokenRepository repository;

    @Test
    void deletesConsumedOrExpiredTokensOlderThanRetentionWindow() {
        Clock clock = Clock.fixed(Instant.parse("2026-07-17T03:00:00Z"), ZoneOffset.UTC);
        UserActionTokenCleanupService service = new UserActionTokenCleanupService(repository, clock);
        when(repository.deleteConsumedOrExpiredBefore(any())).thenReturn(5);

        UserActionTokenCleanupService.CleanupResult result = service.cleanup(30);

        assertThat(result.deletedCount()).isEqualTo(5);
        assertThat(result.retentionDays()).isEqualTo(30);
        assertThat(result.cutoff()).isEqualTo(OffsetDateTime.parse("2026-06-17T03:00:00Z"));
        verify(repository).deleteConsumedOrExpiredBefore(OffsetDateTime.parse("2026-06-17T03:00:00Z"));
    }

    @Test
    void usesDefaultRetentionWhenConfiguredRetentionIsInvalid() {
        Clock clock = Clock.fixed(Instant.parse("2026-07-17T03:00:00Z"), ZoneOffset.UTC);
        UserActionTokenCleanupService service = new UserActionTokenCleanupService(repository, clock);
        when(repository.deleteConsumedOrExpiredBefore(any())).thenReturn(0);

        UserActionTokenCleanupService.CleanupResult result = service.cleanup(0);

        assertThat(result.deletedCount()).isZero();
        assertThat(result.retentionDays()).isEqualTo(30);
        assertThat(result.cutoff()).isEqualTo(OffsetDateTime.parse("2026-06-17T03:00:00Z"));
    }

}
