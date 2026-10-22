package cn.rvport.backend.environment;

import java.util.UUID;

public record JumpHostSummaryResponse(
        UUID id,
        String name,
        String host,
        int sshPort,
        String username,
        boolean enabled
) {
    public static JumpHostSummaryResponse from(EnvironmentView view) {
        if (view == null) {
            return null;
        }
        return new JumpHostSummaryResponse(
                view.id(),
                view.name(),
                view.host(),
                view.sshPort(),
                view.username(),
                view.enabled()
        );
    }
}
