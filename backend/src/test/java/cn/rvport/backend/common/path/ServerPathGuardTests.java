package cn.rvport.backend.common.path;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Arrays;
import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class ServerPathGuardTests {

    @TempDir
    private Path tempDir;

    @Test
    void resolvesExistingFileAndDirectoryUnderRoot() throws Exception {
        Path root = Files.createDirectories(tempDir.resolve("root"));
        Path file = Files.writeString(Files.createDirectories(root.resolve("src")).resolve("main.c"), "int main() {}\n");

        assertThat(ServerPathGuard.resolveExistingFileUnderRoot(root, "src/main.c")).isEqualTo(file.toRealPath());
        assertThat(ServerPathGuard.resolveExistingDirectoryUnderRoot(root, "src")).isEqualTo(file.getParent().toRealPath());
        assertThat(ServerPathGuard.resolveRelativeUnderRoot(root, "build/out")).isEqualTo(root.resolve("build/out").toAbsolutePath().normalize());
    }

    @Test
    void rejectsPathTraversalOutsideRootAndMissingFile() throws Exception {
        Path root = Files.createDirectories(tempDir.resolve("root"));
        Path outside = Files.writeString(tempDir.resolve("secret.txt"), "secret");

        assertThatThrownBy(() -> ServerPathGuard.resolveExistingFileUnderRoot(root, "../secret.txt"))
                .isInstanceOf(ServerPathException.class)
                .hasMessageContaining("outside");
        assertThatThrownBy(() -> ServerPathGuard.resolveExistingFileUnderRoot(root, outside))
                .isInstanceOf(ServerPathException.class)
                .hasMessageContaining("outside");
        assertThatThrownBy(() -> ServerPathGuard.resolveExistingFileUnderRoot(root, "missing.txt"))
                .isInstanceOf(ServerPathException.class);
    }

    @Test
    void rejectsSymlinkEscape() throws Exception {
        Path root = Files.createDirectories(tempDir.resolve("root"));
        Path outside = Files.writeString(tempDir.resolve("secret.txt"), "secret");
        Path link = root.resolve("link.txt");
        try {
            Files.createSymbolicLink(link, outside);
        } catch (UnsupportedOperationException | IOException | SecurityException ex) {
            Assumptions.abort("当前文件系统不支持符号链接测试: " + ex.getMessage());
        }

        assertThatThrownBy(() -> ServerPathGuard.resolveExistingFileUnderRoot(root, "link.txt"))
                .isInstanceOf(ServerPathException.class)
                .hasMessageContaining("outside");
    }

    @Test
    void redactsAllowedRootAndOtherAbsolutePathsFromText() throws Exception {
        Path root = Files.createDirectories(tempDir.resolve("root"));
        String windows = "C:\\Users\\developer\\RvPort\\backend\\runtime\\kb-scans\\scan.log";
        String unix = "/var/lib/rvport/runtime/kb-scans/scan.log";
        String mixed = "see " + root.resolve("src/main.c") + " and " + root.resolve("src\\main.c") + " plus " + windows + " and " + unix;

        String sanitized = ServerPathGuard.redactPathText(mixed, root, "<root>");

        assertThat(sanitized).contains("<root>");
        assertThat(sanitized).contains("<server-path-redacted>");
        assertThat(sanitized).doesNotContain(root.toString());
        assertThat(sanitized).doesNotContain(root.toString().replace('\\', '/'));
        assertThat(sanitized).doesNotContain(windows);
        assertThat(sanitized).doesNotContain(unix);
    }

    @Test
    void redactsOnlyKnownRootsWithoutChangingRelativeSourceText() throws Exception {
        Path root = Files.createDirectories(tempDir.resolve("root"));
        String sourceText = "#include \"../compat/header.h\" // generated at " + root.resolve("src/main.c");

        String sanitized = ServerPathGuard.redactKnownPathRoots(sourceText, List.of(root), "<root>");

        assertThat(sanitized).contains("#include \"../compat/header.h\"");
        assertThat(sanitized).contains("<root>");
        assertThat(sanitized).doesNotContain(root.toString());
    }

    @Test
    void rejectsBlankAbsoluteWindowsAndTraversalRelativePaths() throws Exception {
        Path root = Files.createDirectories(tempDir.resolve("root"));
        for (String candidate : Arrays.asList(null, "", " ", "/etc/passwd", "C:\\Windows\\system.ini",
                "src/../secret", "src\\..\\secret")) {
            assertThatThrownBy(() -> ServerPathGuard.resolveRelativeUnderRoot(root, candidate))
                    .as(String.valueOf(candidate)).isInstanceOf(ServerPathException.class);
        }
        assertThat(ServerPathGuard.resolveRelativeUnderRoot(root, "src\\main.c"))
                .isEqualTo(root.resolve("src/main.c").toAbsolutePath().normalize());
    }

    @Test
    void distinguishesFilesDirectoriesAndMissingRelativeFiles() throws Exception {
        Path root = Files.createDirectories(tempDir.resolve("root"));
        Path directory = Files.createDirectories(root.resolve("dir"));
        Path file = Files.writeString(root.resolve("file.txt"), "content");

        assertThatThrownBy(() -> ServerPathGuard.resolveExistingFileUnderRoot(root, "dir"))
                .isInstanceOf(ServerPathException.class).hasMessageContaining("regular file");
        assertThatThrownBy(() -> ServerPathGuard.resolveExistingDirectoryUnderRoot(root, "file.txt"))
                .isInstanceOf(ServerPathException.class).hasMessageContaining("directory");
        assertThatThrownBy(() -> ServerPathGuard.resolveExistingRelativeFileUnderRoot(root, "missing.txt"))
                .isInstanceOf(ServerPathException.class).hasMessageContaining("does not exist");
        assertThat(ServerPathGuard.resolveExistingRelativeFileUnderRoot(root, "file.txt")).isEqualTo(file.toRealPath());
        assertThat(ServerPathGuard.resolveExistingDirectoryUnderRoot(root, directory.toString())).isEqualTo(directory.toRealPath());
        assertThatThrownBy(() -> ServerPathGuard.resolveExistingFileUnderRoot(root, (Path) null))
                .isInstanceOf(ServerPathException.class).hasMessageContaining("blank");
    }

    @Test
    void rejectsInvalidRootsAndBlankExistingCandidates() throws Exception {
        Path missingRoot = tempDir.resolve("missing-root");
        Path fileRoot = Files.writeString(tempDir.resolve("root-file"), "not-directory");
        for (String candidate : Arrays.asList(null, "", " ")) {
            assertThatThrownBy(() -> ServerPathGuard.resolveExistingFileUnderRoot(tempDir, candidate))
                    .isInstanceOf(ServerPathException.class).hasMessageContaining("blank");
        }
        assertThatThrownBy(() -> ServerPathGuard.resolveExistingFileUnderRoot(null, "file"))
                .isInstanceOf(ServerPathException.class).hasMessageContaining("Root is blank");
        assertThatThrownBy(() -> ServerPathGuard.resolveExistingFileUnderRoot(missingRoot, "file"))
                .isInstanceOf(ServerPathException.class).hasMessageContaining("Root is not a directory");
        assertThatThrownBy(() -> ServerPathGuard.resolveExistingFileUnderRoot(fileRoot, "file"))
                .isInstanceOf(ServerPathException.class).hasMessageContaining("Root is not a directory");
    }

    @Test
    void redactionHandlesNullBlankRootsAndDefaultReplacement() throws Exception {
        Path root = Files.createDirectories(tempDir.resolve("root"));
        assertThat(ServerPathGuard.redactPathText(null, root, null)).isNull();
        assertThat(ServerPathGuard.redactPathText(" ", root, null)).isEqualTo(" ");
        assertThat(ServerPathGuard.redactKnownPathRoots(null, List.of(), null)).isNull();
        assertThat(ServerPathGuard.redactKnownPathRoots("", List.of(), null)).isEmpty();

        String absolute = root.resolve("src/main.c").toString();
        assertThat(ServerPathGuard.redactPathText(absolute, (java.util.Collection<Path>) null, " "))
                .contains("<server-path-redacted>");
        assertThat(ServerPathGuard.redactPathText(absolute, Arrays.asList(null, root), null))
                .isEqualTo("<server-path-redacted>");
        assertThat(ServerPathGuard.redactKnownPathRoots(absolute, null, "custom")).isEqualTo(absolute);
        assertThat(ServerPathGuard.redactKnownPathRoots(absolute, Arrays.asList(null, root), " "))
                .isEqualTo("<server-path-redacted>");
        assertThat(ServerPathGuard.redactKnownPathRoots("relative/path", List.of(Path.of("")), "x"))
                .isEqualTo("relative/path");
    }
}
