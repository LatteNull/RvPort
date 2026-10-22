package cn.rvport.backend.auth;

public record CsrfTokenResponse(
        String headerName,
        String parameterName,
        String token
) {
}
