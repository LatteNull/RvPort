package cn.rvport.backend.source;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.common.error.ApiException;
import org.junit.jupiter.api.Test;

class GitUrlValidatorTests {

    private final GitUrlValidator validator = new GitUrlValidator();

    @Test
    void acceptsNormalHttpsGitUrl() {
        assertThat(validator.sanitize(" https://example.com/repo.git "))
                .isEqualTo("https://example.com/repo.git");
    }

    @Test
    void appendsGitSuffixForHttpsUrlWithoutSuffix() {
        assertThat(validator.sanitize("https://example.com/org/repo"))
                .isEqualTo("https://example.com/org/repo.git");
    }

    @Test
    void trimsTrailingSlashAndDoesNotDuplicateGitSuffix() {
        assertThat(validator.sanitize("https://example.com/org/repo/"))
                .isEqualTo("https://example.com/org/repo.git");
        assertThat(validator.sanitize("https://example.com/org/repo.git/"))
                .isEqualTo("https://example.com/org/repo.git");
    }

    @Test
    void leavesHttpUrlWithQueryOrFragmentUnchangedAfterSafetyCheck() {
        assertThat(validator.sanitize("https://example.com/org/repo?ref=main"))
                .isEqualTo("https://example.com/org/repo?ref=main");
        assertThat(validator.sanitize("https://example.com/org/repo#readme"))
                .isEqualTo("https://example.com/org/repo#readme");
    }

    @Test
    void rejectsCredentialsInHttpGitUrl() {
        assertThatThrownBy(() -> validator.sanitize("https://user:secret@example.com/repo.git"))
                .isInstanceOf(ApiException.class)
                .hasMessage("Git URL 不能包含用户名、密码或 token");
    }

    @Test
    void rejectsBlankGitUrl() {
        assertThatThrownBy(() -> validator.sanitize(null))
                .isInstanceOf(ApiException.class)
                .hasMessage("Git URL 不能为空");
        assertThatThrownBy(() -> validator.sanitize(" "))
                .isInstanceOf(ApiException.class)
                .hasMessage("Git URL 不能为空");
    }

    @Test
    void allowsSshStyleGitUrlAsEdgeCase() {
        assertThat(validator.sanitize("git@example.com:org/repo.git"))
                .isEqualTo("git@example.com:org/repo.git");
    }

    @Test
    void appendsGitSuffixForSshScpStyleUrl() {
        assertThat(validator.sanitize("git@example.com:org/repo"))
                .isEqualTo("git@example.com:org/repo.git");
        assertThat(validator.sanitize("git@example.com:org/repo/"))
                .isEqualTo("git@example.com:org/repo.git");
    }

    @Test
    void appendsGitSuffixForSshUriStyleUrl() {
        assertThat(validator.sanitize("ssh://git@example.com/org/repo"))
                .isEqualTo("ssh://git@example.com/org/repo.git");
    }

    @Test
    void leavesUnrecognizedUrlUnchanged() {
        assertThat(validator.sanitize("/srv/git/repo"))
                .isEqualTo("/srv/git/repo");
    }

    @Test
    void handlesRootQueryFragmentUppercaseSuffixAndMalformedUris() {
        assertThat(validator.sanitize("http://example.com/repo"))
                .isEqualTo("http://example.com/repo.git");
        assertThat(validator.sanitize("https://example.com"))
                .isEqualTo("https://example.com");
        assertThat(validator.sanitize("https://example.com/"))
                .isEqualTo("https://example.com/");
        assertThat(validator.sanitize("ssh://git@example.com/"))
                .isEqualTo("ssh://git@example.com/");
        assertThat(validator.sanitize("ssh://git@example.com/repo?ref=main"))
                .isEqualTo("ssh://git@example.com/repo?ref=main");
        assertThat(validator.sanitize("ssh://git@example.com/repo#main"))
                .isEqualTo("ssh://git@example.com/repo#main");
        assertThat(validator.sanitize("git@example.com:org/repo?ref=main"))
                .isEqualTo("git@example.com:org/repo?ref=main");
        assertThat(validator.sanitize("git@example.com:org/repo#main"))
                .isEqualTo("git@example.com:org/repo#main");
        assertThat(validator.sanitize("https://example.com/repo.GIT"))
                .isEqualTo("https://example.com/repo.GIT");
        assertThatThrownBy(() -> validator.sanitize("https://example.com/%zz"))
                .isInstanceOf(ApiException.class).hasMessage("Git URL 格式不正确");
        assertThatThrownBy(() -> validator.sanitize("ssh://example.com/%zz"))
                .isInstanceOf(ApiException.class).hasMessage("Git URL 格式不正确");
    }
}
