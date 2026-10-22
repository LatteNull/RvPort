package cn.rvport.backend.security;

import cn.rvport.backend.user.UserStatus;
import cn.rvport.backend.user.UserView;
import java.io.Serializable;
import java.util.Collection;
import java.util.List;
import java.util.UUID;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;

public record RvPortUserPrincipal(
        UUID id,
        String username,
        String displayName,
        String email,
        boolean superAdmin,
        boolean mustChangePassword,
        UserStatus status
) implements Serializable {

    public static RvPortUserPrincipal from(UserView user) {
        return new RvPortUserPrincipal(
                user.id(),
                user.username(),
                user.displayName(),
                user.email(),
                user.superAdmin(),
                user.mustChangePassword(),
                user.status()
        );
    }

    public Collection<? extends GrantedAuthority> authorities() {
        if (superAdmin) {
            return List.of(new SimpleGrantedAuthority("SUPER_ADMIN"));
        }
        return List.of();
    }
}
