package cn.rvport.backend.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.Set;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.filter.OncePerRequestFilter;

public class PasswordChangeRequiredFilter extends OncePerRequestFilter {

    private static final Set<String> ALLOWED_PATHS = Set.of(
            "/api/auth/me",
            "/api/auth/csrf",
            "/api/auth/change-password",
            "/api/auth/profile",
            "/api/auth/logout"
    );

    private final SecurityErrorWriter errorWriter;

    public PasswordChangeRequiredFilter(SecurityErrorWriter errorWriter) {
        this.errorWriter = errorWriter;
    }

    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain
    ) throws ServletException, IOException {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication != null
                && authentication.getPrincipal() instanceof RvPortUserPrincipal principal
                && principal.mustChangePassword()
                && !isAllowed(request)) {
            errorWriter.write(
                    request,
                    response,
                    HttpStatus.FORBIDDEN,
                    "PASSWORD_CHANGE_REQUIRED",
                    "用户必须先修改密码"
            );
            return;
        }
        filterChain.doFilter(request, response);
    }

    private boolean isAllowed(HttpServletRequest request) {
        return ALLOWED_PATHS.contains(request.getRequestURI());
    }
}
