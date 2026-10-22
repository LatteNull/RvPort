package cn.rvport.backend.useraction;

import java.time.Clock;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class UserActionTokenCleanupService {

    private static final Logger log = LoggerFactory.getLogger(UserActionTokenCleanupService.class);

    private final UserActionTokenRepository repository;
    private final Clock clock;

    @Autowired
    public UserActionTokenCleanupService(UserActionTokenRepository repository) {
        this(repository, Clock.systemUTC());
    }

    UserActionTokenCleanupService(UserActionTokenRepository repository, Clock clock) {
        this.repository = repository;
        this.clock = clock;
    }

    @Transactional
    public CleanupResult cleanup(int retentionDays) {
        int normalizedRetentionDays = retentionDays <= 0 ? 30 : retentionDays;
        OffsetDateTime cutoff = OffsetDateTime.now(clock.withZone(ZoneOffset.UTC)).minusDays(normalizedRetentionDays);
        int deletedCount = repository.deleteConsumedOrExpiredBefore(cutoff);
        log.info("Cleaned user action tokens cutoff={} retentionDays={} deletedCount={}",
                cutoff, normalizedRetentionDays, deletedCount);
        return new CleanupResult(cutoff, normalizedRetentionDays, deletedCount);
    }

    public record CleanupResult(
            OffsetDateTime cutoff,
            int retentionDays,
            int deletedCount
    ) {
    }
}
