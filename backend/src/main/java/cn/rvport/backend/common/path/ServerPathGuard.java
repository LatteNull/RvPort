package cn.rvport.backend.common.path;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Collection;
import java.util.List;
import java.util.regex.Pattern;

public final class ServerPathGuard {

    private static final Pattern WINDOWS_ABSOLUTE = Pattern.compile("(?i)^[a-z]:[\\\\/].*");
    private static final Pattern WINDOWS_PATH_IN_TEXT = Pattern.compile("(?i)(?<![A-Za-z0-9])(?:[A-Z]:[\\\\/][^\\s\"'<>|{}\\[\\],;]+)");
    private static final Pattern UNIX_PATH_IN_TEXT = Pattern.compile("(?<![A-Za-z0-9])/(?:[^\\s\"'<>|{}\\[\\],;]+)");
    private static final String DEFAULT_REDACTION = "<server-path-redacted>";

    private ServerPathGuard() {
    }

    public static Path resolveExistingFileUnderRoot(Path root, String candidate) {
        Path resolved = resolveExistingUnderRoot(root, candidate);
        if (!Files.isRegularFile(resolved)) {
            throw new ServerPathException("Path is not a regular file");
        }
        return resolved;
    }

    public static Path resolveExistingFileUnderRoot(Path root, Path candidate) {
        return resolveExistingFileUnderRoot(root, candidate == null ? null : candidate.toString());
    }

    public static Path resolveExistingDirectoryUnderRoot(Path root, String candidate) {
        Path resolved = resolveExistingUnderRoot(root, candidate);
        if (!Files.isDirectory(resolved)) {
            throw new ServerPathException("Path is not a directory");
        }
        return resolved;
    }

    public static Path resolveRelativeUnderRoot(Path root, String relativePath) {
        if (relativePath == null || relativePath.isBlank()) {
            throw new ServerPathException("Path is blank");
        }
        String normalizedInput = relativePath.replace('\\', '/');
        if (normalizedInput.startsWith("/") || WINDOWS_ABSOLUTE.matcher(normalizedInput).matches()) {
            throw new ServerPathException("Absolute path is not allowed");
        }
        for (String part : normalizedInput.split("/")) {
            if ("..".equals(part)) {
                throw new ServerPathException("Path traversal is not allowed");
            }
        }
        Path absoluteRoot = absolute(root);
        Path resolved = absoluteRoot.resolve(normalizedInput).normalize();
        if (!resolved.startsWith(absoluteRoot)) {
            throw new ServerPathException("Path is outside allowed root");
        }
        return resolved;
    }

    public static Path resolveExistingRelativeFileUnderRoot(Path root, String relativePath) {
        Path resolved = resolveRelativeUnderRoot(root, relativePath);
        if (!Files.exists(resolved)) {
            throw new ServerPathException("Path does not exist");
        }
        return resolveExistingFileUnderRoot(root, resolved);
    }

    public static String redactPathText(String text, Path allowedRoot, String replacement) {
        if (text == null || text.isBlank()) {
            return text;
        }
        return redactPathText(text, List.of(allowedRoot), replacement);
    }

    public static String redactPathText(String text, Collection<Path> allowedRoots, String replacement) {
        if (text == null || text.isBlank()) {
            return text;
        }
        String result = text;
        String marker = replacement == null || replacement.isBlank() ? DEFAULT_REDACTION : replacement;
        for (Path root : allowedRoots == null ? List.<Path>of() : allowedRoots) {
            if (root == null) {
                continue;
            }
            String normalizedRoot = absolute(root).toString();
            result = replaceRoot(result, normalizedRoot, marker);
            result = replaceRoot(result, normalizedRoot.replace('\\', '/'), marker);
        }
        result = WINDOWS_PATH_IN_TEXT.matcher(result).replaceAll(DEFAULT_REDACTION);
        result = UNIX_PATH_IN_TEXT.matcher(result).replaceAll(DEFAULT_REDACTION);
        return result;
    }

    public static String redactKnownPathRoots(String text, Collection<Path> roots, String replacement) {
        if (text == null || text.isBlank()) {
            return text;
        }
        String result = text;
        String marker = replacement == null || replacement.isBlank() ? DEFAULT_REDACTION : replacement;
        for (Path root : roots == null ? List.<Path>of() : roots) {
            if (root == null) {
                continue;
            }
            String normalizedRoot = absolute(root).toString();
            result = replaceRoot(result, normalizedRoot, marker);
            result = replaceRoot(result, normalizedRoot.replace('\\', '/'), marker);
        }
        return result;
    }

    private static Path resolveExistingUnderRoot(Path root, String candidate) {
        if (candidate == null || candidate.isBlank()) {
            throw new ServerPathException("Path is blank");
        }
        Path absoluteRoot = realRoot(root);
        Path raw = Path.of(candidate);
        Path normalized = raw.isAbsolute() ? raw.toAbsolutePath().normalize() : absoluteRoot.resolve(raw).normalize();
        Path real = realPath(normalized);
        if (!real.startsWith(absoluteRoot)) {
            throw new ServerPathException("Path is outside allowed root");
        }
        return real;
    }

    private static Path realRoot(Path root) {
        Path absoluteRoot = absolute(root);
        if (!Files.isDirectory(absoluteRoot)) {
            throw new ServerPathException("Root is not a directory");
        }
        return realPath(absoluteRoot);
    }

    private static Path realPath(Path path) {
        try {
            return path.toRealPath();
        } catch (IOException ex) {
            throw new ServerPathException("Path cannot be resolved");
        }
    }

    private static Path absolute(Path path) {
        if (path == null) {
            throw new ServerPathException("Root is blank");
        }
        return path.toAbsolutePath().normalize();
    }

    private static String replaceRoot(String text, String root, String replacement) {
        if (root == null || root.isBlank()) {
            return text;
        }
        String escaped = Pattern.quote(root);
        return Pattern.compile(escaped + "([\\\\/][^\\s\"'<>|{}\\[\\],;]*)?")
                .matcher(text)
                .replaceAll(replacement);
    }
}
