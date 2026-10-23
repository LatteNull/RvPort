package cn.rvport.backend.report.runtime;

import cn.rvport.backend.migration.MigrationInputRefView;
import cn.rvport.backend.report.ReportInputProjection;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import org.springframework.stereotype.Component;

@Component
public class ReportOrganizationProjector {

    private static final Set<String> BUILD_DESCRIPTORS = Set.of(
            "CMakeLists.txt", "meson.build", "Makefile", "makefile", "GNUmakefile"
    );

    public ReportInputProjection project(MigrationInputRefView ref, Map<String, Object> snapshot, Path sourceRoot) {
        String sourceType = ref.sourceType().name();
        String risk = riskToken(ref.detectedLevel());
        if (!isCodeFinding(sourceType)) {
            return ReportInputProjection.none(sourceType, risk);
        }

        Map<String, Object> detail = map(snapshot.get("sourceDetail"));
        String path = normalizedRelativePath(sourceRoot, text(detail.get("filePath")));
        String findingType = firstNonBlank(text(detail.get("category")), ref.ruleId(), "UNCLASSIFIED");
        Integer lineStart = positiveInteger(detail.get("lineStart"));
        Integer lineEnd = positiveInteger(detail.get("lineEnd"));
        Integer columnStart = positiveInteger(first(detail, "columnStart", "colStart", "startColumn"));
        Integer columnEnd = positiveInteger(first(detail, "columnEnd", "colEnd", "endColumn"));

        if (path == null) {
            return new ReportInputProjection(sourceType, risk, "unlocated", "未定位", "UNLOCATED", "LOW", List.of(),
                    "unlocated", null, findingType, lineStart, lineEnd, columnStart, columnEnd,
                    firstNonBlank(text(detail.get("symbol")), ref.identitySymbol()), null, false);
        }

        Module module = resolveModule(sourceRoot, path, detail);
        return new ReportInputProjection(
                sourceType,
                risk,
                module.key(),
                module.name(),
                module.basis(),
                module.confidence(),
                module.relatedKeys(),
                hash("file:" + path),
                path,
                findingType,
                lineStart,
                lineEnd == null ? lineStart : lineEnd,
                columnStart,
                columnEnd,
                firstNonBlank(text(detail.get("symbol")), ref.identitySymbol()),
                null,
                lineStart != null
        );
    }

    private boolean isCodeFinding(String sourceType) {
        return "KB_FINDING".equals(sourceType)
                || "FLOATING_POINT_FINDING".equals(sourceType)
                || "MEMORY_ORDER_FINDING".equals(sourceType);
    }

    private Module resolveModule(Path sourceRoot, String relativePath, Map<String, Object> detail) {
        List<String> targets = targetNames(detail);
        if (targets.size() > 1) {
            List<String> keys = targets.stream().map(target -> hash("target:" + target)).sorted().toList();
            String sharedName = "共享代码 (" + String.join(", ", targets) + ")";
            return new Module(hash("shared:" + String.join("|", targets)), sharedName, "EXPLICIT_BUILD_TARGET", "HIGH", keys);
        }
        if (targets.size() == 1) {
            String target = targets.getFirst();
            return new Module(hash("target:" + target), target, "EXPLICIT_BUILD_TARGET", "HIGH", List.of());
        }

        String artifact = firstNonBlankOrNull(text(detail.get("buildArtifact")), text(detail.get("linkArtifact")));
        if (artifact != null) {
            String normalized = artifact.replace('\\', '/');
            String name = Path.of(normalized).getFileName().toString();
            return new Module(hash("artifact:" + normalized), name, "BUILD_ARTIFACT", "HIGH", List.of());
        }

        Descriptor descriptor = nearestDescriptor(sourceRoot, relativePath);
        if (descriptor != null) {
            String logical = descriptor.directory().isBlank() ? "project-root" : descriptor.directory();
            String name = descriptor.directory().isBlank() ? "项目根模块" : descriptor.directory();
            return new Module(hash("descriptor:" + logical), name, "NEAREST_BUILD_DESCRIPTOR", "MEDIUM", List.of());
        }

        int slash = relativePath.indexOf('/');
        if (slash > 0) {
            String directory = relativePath.substring(0, slash);
            return new Module(hash("directory:" + directory), directory, "DIRECTORY", "LOW", List.of());
        }
        return new Module(hash("root"), "项目根模块", "PROJECT_ROOT", "LOW", List.of());
    }

    private List<String> targetNames(Map<String, Object> detail) {
        LinkedHashSet<String> result = new LinkedHashSet<>();
        addTarget(result, detail.get("buildTarget"));
        addTarget(result, detail.get("buildTargets"));
        Map<String, Object> evidence = map(detail.get("evidence"));
        addTarget(result, evidence.get("buildTarget"));
        addTarget(result, evidence.get("buildTargets"));
        return result.stream().sorted(String.CASE_INSENSITIVE_ORDER).toList();
    }

    private void addTarget(Set<String> result, Object value) {
        if (value instanceof Iterable<?> iterable) {
            for (Object item : iterable) {
                String target = text(item);
                if (target != null) {
                    result.add(target);
                }
            }
        } else {
            String target = text(value);
            if (target != null) {
                result.add(target);
            }
        }
    }

    private Descriptor nearestDescriptor(Path sourceRoot, String relativePath) {
        if (sourceRoot == null || !Files.isDirectory(sourceRoot)) {
            return null;
        }
        Path parent = Path.of(relativePath).getParent();
        while (parent != null) {
            Path directory = sourceRoot.resolve(parent).normalize();
            for (String descriptor : BUILD_DESCRIPTORS) {
                if (Files.isRegularFile(directory.resolve(descriptor))) {
                    return new Descriptor(parent.toString().replace('\\', '/'));
                }
            }
            try (var stream = Files.isDirectory(directory) ? Files.list(directory) : null) {
                if (stream != null && stream.anyMatch(path -> path.getFileName().toString().endsWith(".spec"))) {
                    return new Descriptor(parent.toString().replace('\\', '/'));
                }
            } catch (Exception ignored) {
                return null;
            }
            parent = parent.getParent();
        }
        for (String descriptor : BUILD_DESCRIPTORS) {
            if (Files.isRegularFile(sourceRoot.resolve(descriptor))) {
                return new Descriptor("");
            }
        }
        return null;
    }

    private String normalizedRelativePath(Path sourceRoot, String candidate) {
        if (candidate == null) {
            return null;
        }
        String normalized = candidate.trim().replace('\\', '/');
        if (normalized.startsWith("<source-root>/")) {
            normalized = normalized.substring("<source-root>/".length());
        }
        try {
            Path raw = Path.of(normalized);
            if (raw.isAbsolute()) {
                if (sourceRoot == null) {
                    return null;
                }
                Path root = sourceRoot.toAbsolutePath().normalize();
                Path absolute = raw.toAbsolutePath().normalize();
                if (!absolute.startsWith(root)) {
                    return null;
                }
                normalized = root.relativize(absolute).toString().replace('\\', '/');
            }
            Path relative = Path.of(normalized).normalize();
            if (relative.isAbsolute() || relative.startsWith("..") || normalized.isBlank()) {
                return null;
            }
            return relative.toString().replace('\\', '/');
        } catch (RuntimeException ex) {
            return null;
        }
    }

    private String riskToken(String value) {
        String normalized = firstNonBlank(value, "INFO").toUpperCase(Locale.ROOT);
        int slash = normalized.indexOf('/');
        return slash < 0 ? normalized : normalized.substring(0, slash);
    }

    private String hash(String value) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(StandardCharsets.UTF_8))).substring(0, 24);
        } catch (Exception ex) {
            throw new IllegalStateException("SHA-256 is not available", ex);
        }
    }

    private Integer positiveInteger(Object value) {
        if (value instanceof Number number && number.intValue() > 0) {
            return number.intValue();
        }
        try {
            int parsed = value == null ? 0 : Integer.parseInt(String.valueOf(value));
            return parsed > 0 ? parsed : null;
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    private Object first(Map<String, Object> values, String... keys) {
        for (String key : keys) {
            if (values.get(key) != null) {
                return values.get(key);
            }
        }
        return null;
    }

    private Map<String, Object> map(Object value) {
        if (!(value instanceof Map<?, ?> source)) {
            return Map.of();
        }
        java.util.LinkedHashMap<String, Object> result = new java.util.LinkedHashMap<>();
        source.forEach((key, item) -> result.put(String.valueOf(key), item));
        return result;
    }

    private String text(Object value) {
        String text = value == null ? null : String.valueOf(value).trim();
        return text == null || text.isBlank() ? null : text;
    }

    private String firstNonBlank(String... values) {
        String value = firstNonBlankOrNull(values);
        return value == null ? "" : value;
    }

    private String firstNonBlankOrNull(String... values) {
        for (String value : values) {
            if (value != null && !value.isBlank()) {
                return value.trim();
            }
        }
        return null;
    }

    private record Module(String key, String name, String basis, String confidence, List<String> relatedKeys) {
    }

    private record Descriptor(String directory) {
    }
}
