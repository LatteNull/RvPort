package cn.rvport.backend.source;

import cn.rvport.backend.common.error.ApiException;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.Locale;
import java.util.regex.Pattern;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;

@Component
public class GitUrlValidator {

    private static final Pattern SCP_STYLE_URL = Pattern.compile("^[^\\s@]+@[^\\s:]+:.+");

    public String sanitize(String gitUrl) {
        if (gitUrl == null || gitUrl.isBlank()) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "GIT_URL_REQUIRED", "Git URL 不能为空");
        }
        String trimmed = gitUrl.trim();
        if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
            validateHttpUrl(trimmed);
            return normalizeHttpUrl(trimmed);
        }
        if (trimmed.startsWith("ssh://")) {
            return normalizeUriStyleUrl(trimmed);
        }
        if (SCP_STYLE_URL.matcher(trimmed).matches()) {
            return normalizeScpStyleUrl(trimmed);
        }
        return trimmed;
    }

    private void validateHttpUrl(String gitUrl) {
        try {
            URI uri = new URI(gitUrl);
            if (uri.getUserInfo() != null && !uri.getUserInfo().isBlank()) {
                throw credentialInUrl();
            }
            String rawAuthority = uri.getRawAuthority();
            if (rawAuthority != null && rawAuthority.contains("@")) {
                throw credentialInUrl();
            }
        } catch (URISyntaxException ex) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "GIT_URL_INVALID", "Git URL 格式不正确");
        }
    }

    private ApiException credentialInUrl() {
        return new ApiException(HttpStatus.BAD_REQUEST, "GIT_URL_CONTAINS_CREDENTIAL", "Git URL 不能包含用户名、密码或 token");
    }

    private String normalizeHttpUrl(String gitUrl) {
        try {
            URI uri = new URI(gitUrl);
            if (uri.getRawQuery() != null || uri.getRawFragment() != null) {
                return gitUrl;
            }
            String normalizedPath = normalizeRepositoryPath(uri.getRawPath());
            if (normalizedPath == null) {
                return gitUrl;
            }
            return new URI(uri.getScheme(), null, uri.getHost(), uri.getPort(), normalizedPath, null, null).toString();
        } catch (URISyntaxException ex) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "GIT_URL_INVALID", "Git URL 格式不正确");
        }
    }

    private String normalizeUriStyleUrl(String gitUrl) {
        try {
            URI uri = new URI(gitUrl);
            if (uri.getRawQuery() != null || uri.getRawFragment() != null) {
                return gitUrl;
            }
            String normalizedPath = normalizeRepositoryPath(uri.getRawPath());
            if (normalizedPath == null) {
                return gitUrl;
            }
            return new URI(uri.getScheme(), uri.getRawUserInfo(), uri.getHost(), uri.getPort(), normalizedPath, null, null).toString();
        } catch (URISyntaxException ex) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "GIT_URL_INVALID", "Git URL 格式不正确");
        }
    }

    private String normalizeScpStyleUrl(String gitUrl) {
        if (gitUrl.contains("?") || gitUrl.contains("#")) {
            return gitUrl;
        }
        String normalized = trimTrailingSlashes(gitUrl);
        return endsWithGit(normalized) ? normalized : normalized + ".git";
    }

    private String normalizeRepositoryPath(String rawPath) {
        if (rawPath == null || rawPath.isBlank() || "/".equals(rawPath)) {
            return null;
        }
        String normalized = trimTrailingSlashes(rawPath);
        return endsWithGit(normalized) ? normalized : normalized + ".git";
    }

    private String trimTrailingSlashes(String value) {
        String result = value;
        while (result.endsWith("/") && result.length() > 1) {
            result = result.substring(0, result.length() - 1);
        }
        return result;
    }

    private boolean endsWithGit(String value) {
        return value.toLowerCase(Locale.ROOT).endsWith(".git");
    }
}
