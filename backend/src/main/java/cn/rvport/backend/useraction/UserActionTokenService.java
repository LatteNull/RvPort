package cn.rvport.backend.useraction;

import cn.rvport.backend.common.error.ApiException;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.time.Duration;
import java.time.OffsetDateTime;
import java.util.Base64;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class UserActionTokenService {

    private static final Duration INVITATION_TTL = Duration.ofHours(24);
    private static final Duration PASSWORD_RESET_TTL = Duration.ofHours(1);

    private final UserActionTokenRepository repository;
    private final SecureRandom secureRandom = new SecureRandom();

    public UserActionTokenService(UserActionTokenRepository repository) {
        this.repository = repository;
    }

    @Transactional
    public IssuedToken issueInvitation(UUID userId, UUID actorUserId) {
        return issue(userId, UserActionTokenType.INVITATION, INVITATION_TTL, actorUserId, true);
    }

    @Transactional
    public IssuedToken issuePasswordReset(UUID userId) {
        return issue(userId, UserActionTokenType.PASSWORD_RESET, PASSWORD_RESET_TTL, null, true);
    }

    public UserActionTokenView requireOpen(String plainToken, UserActionTokenType type) {
        return repository.findOpenByHash(hash(plainToken), type, OffsetDateTime.now())
                .orElseThrow(() -> new ApiException(HttpStatus.BAD_REQUEST, "ACTION_TOKEN_INVALID", "链接无效或已过期"));
    }

    public void consume(UUID tokenId) {
        if (!repository.consume(tokenId)) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "ACTION_TOKEN_INVALID", "链接无效或已过期");
        }
    }

    private IssuedToken issue(UUID userId, UserActionTokenType type, Duration ttl, UUID createdBy, boolean invalidateExisting) {
        if (invalidateExisting) {
            repository.consumeOpenTokens(userId, type);
        }
        String token = randomToken();
        UserActionTokenView view = repository.create(userId, type, hash(token), OffsetDateTime.now().plus(ttl), createdBy);
        return new IssuedToken(token, view);
    }

    private String randomToken() {
        byte[] bytes = new byte[32];
        secureRandom.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }

    private String hash(String token) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(token.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            return Base64.getUrlEncoder().withoutPadding().encodeToString(digest);
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException(ex);
        }
    }

    public record IssuedToken(
            String plainToken,
            UserActionTokenView view
    ) {
    }
}
