package cn.rvport.backend.security;

import cn.rvport.backend.user.UserRepository;
import cn.rvport.backend.user.UserStatus;
import cn.rvport.backend.user.UserView;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import org.springframework.http.HttpStatus;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.filter.OncePerRequestFilter;

public class CurrentUserStatusFilter extends OncePerRequestFilter {

    private final UserRepository userRepository;
    private final SecurityErrorWriter errorWriter;

    public CurrentUserStatusFilter(UserRepository userRepository, SecurityErrorWriter errorWriter) {
        this.userRepository = userRepository;
        this.errorWriter = errorWriter;
    }

    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain
    ) throws ServletException, IOException {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication == null || !(authentication.getPrincipal() instanceof RvPortUserPrincipal principal)) {
            filterChain.doFilter(request, response);
            return;
        }

        UserView current = userRepository.findById(principal.id()).orElse(null);
        if (current == null || current.status() != UserStatus.ACTIVE) {
            SecurityContextHolder.clearContext();
            if (request.getSession(false) != null) {
                request.getSession(false).invalidate();
            }
            errorWriter.write(request, response, HttpStatus.UNAUTHORIZED, "AUTH_REQUIRED", "登录态已失效");
            return;
        }

        RvPortUserPrincipal refreshed = RvPortUserPrincipal.from(current);
        UsernamePasswordAuthenticationToken updated = UsernamePasswordAuthenticationToken.authenticated(
                refreshed,
                null,
                refreshed.authorities()
        );
        updated.setDetails(authentication.getDetails());
        SecurityContextHolder.getContext().setAuthentication(updated);
        filterChain.doFilter(request, response);
    }
}
