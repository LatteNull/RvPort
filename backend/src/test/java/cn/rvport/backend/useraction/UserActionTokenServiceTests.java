package cn.rvport.backend.useraction;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.common.error.ApiException;
import java.time.OffsetDateTime;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class UserActionTokenServiceTests {

    @Mock
    private UserActionTokenRepository repository;

    @Test
    void issuesInvitationWithHashAndInvalidatesOldTokens() {
        UserActionTokenService service = new UserActionTokenService(repository);
        UUID userId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        ArgumentCaptor<String> hashCaptor = ArgumentCaptor.forClass(String.class);
        when(repository.create(eq(userId), eq(UserActionTokenType.INVITATION), hashCaptor.capture(), any(), eq(actorId)))
                .thenAnswer(invocation -> token(userId, UserActionTokenType.INVITATION, invocation.getArgument(2)));

        UserActionTokenService.IssuedToken issued = service.issueInvitation(userId, actorId);

        assertThat(issued.plainToken()).isNotBlank();
        assertThat(hashCaptor.getValue()).isNotEqualTo(issued.plainToken());
        verify(repository).consumeOpenTokens(userId, UserActionTokenType.INVITATION);
    }

    @Test
    void rejectsMissingOpenTokenAndConsumesAtomically() {
        UserActionTokenService service = new UserActionTokenService(repository);
        when(repository.findOpenByHash(any(), eq(UserActionTokenType.PASSWORD_RESET), any())).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.requireOpen("bad", UserActionTokenType.PASSWORD_RESET))
                .isInstanceOf(ApiException.class)
                .hasMessage("链接无效或已过期");

        UUID tokenId = UUID.randomUUID();
        when(repository.consume(tokenId)).thenReturn(false);
        assertThatThrownBy(() -> service.consume(tokenId))
                .isInstanceOf(ApiException.class)
                .hasMessage("链接无效或已过期");
    }

    @Test
    void issuesPasswordResetFindsAndConsumesValidToken() {
        UserActionTokenService service = new UserActionTokenService(repository);
        UUID userId = UUID.randomUUID();
        ArgumentCaptor<String> hashCaptor = ArgumentCaptor.forClass(String.class);
        when(repository.create(eq(userId), eq(UserActionTokenType.PASSWORD_RESET), hashCaptor.capture(), any(), eq(null)))
                .thenAnswer(invocation -> token(userId, UserActionTokenType.PASSWORD_RESET, invocation.getArgument(2)));

        UserActionTokenService.IssuedToken issued = service.issuePasswordReset(userId);
        when(repository.findOpenByHash(eq(hashCaptor.getValue()), eq(UserActionTokenType.PASSWORD_RESET), any()))
                .thenReturn(Optional.of(issued.view()));
        when(repository.consume(issued.view().id())).thenReturn(true);

        assertThat(service.requireOpen(issued.plainToken(), UserActionTokenType.PASSWORD_RESET))
                .isEqualTo(issued.view());
        service.consume(issued.view().id());
        verify(repository).consumeOpenTokens(userId, UserActionTokenType.PASSWORD_RESET);
        verify(repository).consume(issued.view().id());
    }

    private UserActionTokenView token(UUID userId, UserActionTokenType type, String hash) {
        return new UserActionTokenView(UUID.randomUUID(), userId, type, hash,
                OffsetDateTime.now().plusHours(1), null, null, OffsetDateTime.now());
    }
}
