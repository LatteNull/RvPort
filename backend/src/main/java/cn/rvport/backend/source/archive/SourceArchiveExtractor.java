package cn.rvport.backend.source.archive;

import com.github.junrar.Archive;
import com.github.junrar.exception.RarException;
import com.github.junrar.rarfile.FileHeader;
import java.io.BufferedInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.Comparator;
import java.util.Locale;
import java.util.regex.Pattern;
import org.apache.commons.compress.archivers.ArchiveEntry;
import org.apache.commons.compress.archivers.sevenz.SevenZArchiveEntry;
import org.apache.commons.compress.archivers.sevenz.SevenZFile;
import org.apache.commons.compress.archivers.tar.TarArchiveInputStream;
import org.apache.commons.compress.archivers.zip.ZipArchiveInputStream;
import org.apache.commons.compress.compressors.gzip.GzipCompressorInputStream;
import org.apache.commons.compress.compressors.xz.XZCompressorInputStream;
import org.springframework.stereotype.Component;

@Component
public class SourceArchiveExtractor {

    private static final Pattern WINDOWS_ABSOLUTE = Pattern.compile("^[A-Za-z]:[/\\\\].*");

    public SourceArchiveExtraction extract(Path archiveFile, String originalFilename, Path targetDir) {
        ArchiveFormat format = ArchiveFormat.detect(originalFilename, archiveFile);
        Path absoluteTarget = targetDir.toAbsolutePath().normalize();
        Path tempDir = absoluteTarget.resolveSibling("." + absoluteTarget.getFileName() + ".tmp").normalize();
        try {
            deleteRecursively(tempDir);
            deleteRecursively(absoluteTarget);
            Files.createDirectories(tempDir);
            int fileCount = switch (format) {
                case ZIP -> extractZip(archiveFile, tempDir);
                case SEVEN_Z -> extractSevenZip(archiveFile, tempDir);
                case RAR -> extractRar(archiveFile, tempDir);
                case TAR_GZ -> extractTarGz(archiveFile, tempDir);
                case TAR_XZ -> extractTarXz(archiveFile, tempDir);
                case GZIP -> extractGzip(archiveFile, originalFilename, tempDir);
            };
            if (fileCount <= 0) {
                throw new SourceArchiveException(SourceArchiveErrorCode.SOURCE_ARCHIVE_EMPTY, "源码包没有可用文件");
            }
            Files.createDirectories(absoluteTarget.getParent());
            move(tempDir, absoluteTarget);
            return new SourceArchiveExtraction(absoluteTarget, fileCount);
        } catch (SourceArchiveException ex) {
            deleteRecursively(tempDir);
            deleteRecursively(absoluteTarget);
            throw ex;
        } catch (IOException | RarException ex) {
            deleteRecursively(tempDir);
            deleteRecursively(absoluteTarget);
            throw new SourceArchiveException(SourceArchiveErrorCode.SOURCE_ARCHIVE_UNSUPPORTED_STRUCTURE, "源码包结构无效或解包失败", ex);
        }
    }

    private int extractZip(Path archiveFile, Path targetDir) throws IOException {
        int files = 0;
        try (InputStream input = Files.newInputStream(archiveFile);
             ZipArchiveInputStream zip = new ZipArchiveInputStream(new BufferedInputStream(input))) {
            ArchiveEntry entry;
            while ((entry = zip.getNextEntry()) != null) {
                if (!zip.canReadEntryData(entry)) {
                    throw new SourceArchiveException(SourceArchiveErrorCode.SOURCE_ARCHIVE_UNSUPPORTED_STRUCTURE, "源码包包含不可读取条目");
                }
                if (extractStreamEntry(zip, targetDir, entry.getName(), entry.isDirectory())) {
                    files++;
                }
            }
        }
        return files;
    }

    private int extractTarGz(Path archiveFile, Path targetDir) throws IOException {
        try (InputStream input = Files.newInputStream(archiveFile);
             GzipCompressorInputStream gzip = new GzipCompressorInputStream(new BufferedInputStream(input));
             TarArchiveInputStream tar = new TarArchiveInputStream(gzip)) {
            return extractTar(tar, targetDir);
        }
    }

    private int extractTarXz(Path archiveFile, Path targetDir) throws IOException {
        try (InputStream input = Files.newInputStream(archiveFile);
             XZCompressorInputStream xz = new XZCompressorInputStream(new BufferedInputStream(input));
             TarArchiveInputStream tar = new TarArchiveInputStream(xz)) {
            return extractTar(tar, targetDir);
        }
    }

    private int extractTar(TarArchiveInputStream tar, Path targetDir) throws IOException {
        int files = 0;
        ArchiveEntry entry;
        while ((entry = tar.getNextEntry()) != null) {
            if (!tar.canReadEntryData(entry)) {
                throw new SourceArchiveException(SourceArchiveErrorCode.SOURCE_ARCHIVE_UNSUPPORTED_STRUCTURE, "源码包包含不可读取条目");
            }
            if (extractStreamEntry(tar, targetDir, entry.getName(), entry.isDirectory())) {
                files++;
            }
        }
        return files;
    }

    private int extractSevenZip(Path archiveFile, Path targetDir) throws IOException {
        int files = 0;
        try (SevenZFile sevenZ = new SevenZFile(archiveFile.toFile())) {
            SevenZArchiveEntry entry;
            byte[] buffer = new byte[8192];
            while ((entry = sevenZ.getNextEntry()) != null) {
                Path output = safeEntryPath(targetDir, entry.getName());
                if (entry.isDirectory()) {
                    Files.createDirectories(output);
                    continue;
                }
                Files.createDirectories(output.getParent());
                try (OutputStream out = Files.newOutputStream(output)) {
                    int read;
                    while ((read = sevenZ.read(buffer)) > 0) {
                        out.write(buffer, 0, read);
                    }
                }
                files++;
            }
        }
        return files;
    }

    private int extractRar(Path archiveFile, Path targetDir) throws IOException, RarException {
        int files = 0;
        try (Archive archive = new Archive(archiveFile.toFile())) {
            FileHeader header;
            while ((header = archive.nextFileHeader()) != null) {
                String name = header.getFileNameString();
                Path output = safeEntryPath(targetDir, name);
                if (header.isDirectory()) {
                    Files.createDirectories(output);
                    continue;
                }
                Files.createDirectories(output.getParent());
                try (OutputStream out = Files.newOutputStream(output)) {
                    archive.extractFile(header, out);
                }
                files++;
            }
        }
        return files;
    }

    private int extractGzip(Path archiveFile, String originalFilename, Path targetDir) throws IOException {
        String outputName = gzipOutputName(originalFilename);
        if (outputName == null) {
            throw new SourceArchiveException(SourceArchiveErrorCode.SOURCE_ARCHIVE_UNSUPPORTED_STRUCTURE, "gzip 源码包无法形成可用文件名");
        }
        Path output = safeEntryPath(targetDir, outputName);
        Files.createDirectories(output.getParent());
        try (InputStream input = Files.newInputStream(archiveFile);
             GzipCompressorInputStream gzip = new GzipCompressorInputStream(new BufferedInputStream(input));
             OutputStream out = Files.newOutputStream(output)) {
            gzip.transferTo(out);
        }
        return Files.size(output) > 0 ? 1 : 0;
    }

    private boolean extractStreamEntry(InputStream input, Path targetDir, String entryName, boolean directory) throws IOException {
        Path output = safeEntryPath(targetDir, entryName);
        if (directory) {
            Files.createDirectories(output);
            return false;
        }
        Files.createDirectories(output.getParent());
        Files.copy(input, output, StandardCopyOption.REPLACE_EXISTING);
        return true;
    }

    private Path safeEntryPath(Path targetDir, String entryName) {
        if (entryName == null || entryName.isBlank()) {
            throw new SourceArchiveException(SourceArchiveErrorCode.SOURCE_ARCHIVE_UNSAFE_PATH, "源码包包含空路径条目");
        }
        String normalizedName = entryName.replace('\\', '/');
        if (normalizedName.startsWith("/") || WINDOWS_ABSOLUTE.matcher(normalizedName).matches()) {
            throw new SourceArchiveException(SourceArchiveErrorCode.SOURCE_ARCHIVE_UNSAFE_PATH, "源码包包含绝对路径条目");
        }
        for (String part : normalizedName.split("/")) {
            if (part.equals("..")) {
                throw new SourceArchiveException(SourceArchiveErrorCode.SOURCE_ARCHIVE_UNSAFE_PATH, "源码包包含路径逃逸条目");
            }
        }
        Path root = targetDir.toAbsolutePath().normalize();
        Path output = root.resolve(normalizedName).normalize();
        if (!output.startsWith(root)) {
            throw new SourceArchiveException(SourceArchiveErrorCode.SOURCE_ARCHIVE_UNSAFE_PATH, "源码包路径越界");
        }
        return output;
    }

    private String gzipOutputName(String originalFilename) {
        if (originalFilename == null || originalFilename.isBlank()) {
            return null;
        }
        String name = Path.of(originalFilename).getFileName().toString();
        String lower = name.toLowerCase(Locale.ROOT);
        if (lower.endsWith(".gzip")) {
            return name.substring(0, name.length() - 5);
        }
        if (lower.endsWith(".gz")) {
            String stripped = name.substring(0, name.length() - 3);
            if (stripped.toLowerCase(Locale.ROOT).endsWith(".tar")) {
                return null;
            }
            return stripped;
        }
        return null;
    }

    private void move(Path source, Path target) throws IOException {
        try {
            Files.move(source, target, StandardCopyOption.ATOMIC_MOVE);
        } catch (AtomicMoveNotSupportedException ex) {
            Files.move(source, target);
        }
    }

    private void deleteRecursively(Path path) {
        if (path == null || !Files.exists(path)) {
            return;
        }
        try (var stream = Files.walk(path)) {
            stream.sorted(Comparator.reverseOrder()).forEach(item -> {
                try {
                    Files.deleteIfExists(item);
                } catch (IOException ignored) {
                    // 尽力清理，不覆盖原始错误。
                }
            });
        } catch (IOException ignored) {
            // 同上。
        }
    }

    private enum ArchiveFormat {
        ZIP,
        RAR,
        SEVEN_Z,
        TAR_GZ,
        TAR_XZ,
        GZIP;

        private static ArchiveFormat detect(String originalFilename, Path archiveFile) {
            String lower = originalFilename == null ? "" : originalFilename.toLowerCase(Locale.ROOT);
            if (lower.endsWith(".zip")) {
                return ZIP;
            }
            if (lower.endsWith(".rar")) {
                return RAR;
            }
            if (lower.endsWith(".7z")) {
                return SEVEN_Z;
            }
            if (lower.endsWith(".tar.gz") || lower.endsWith(".tgz")) {
                return TAR_GZ;
            }
            if (lower.endsWith(".tar.xz")) {
                return TAR_XZ;
            }
            if (lower.endsWith(".gzip") || lower.endsWith(".gz")) {
                return GZIP;
            }
            ArchiveFormat byMagic = detectByMagic(archiveFile);
            if (byMagic != null) {
                return byMagic;
            }
            throw new SourceArchiveException(SourceArchiveErrorCode.SOURCE_ARCHIVE_UNSUPPORTED_FORMAT, "不支持的源码包格式");
        }

        private static ArchiveFormat detectByMagic(Path archiveFile) {
            try (InputStream input = Files.newInputStream(archiveFile)) {
                byte[] magic = input.readNBytes(8);
                if (magic.length >= 4 && magic[0] == 0x50 && magic[1] == 0x4b) {
                    return ZIP;
                }
                if (magic.length >= 6
                        && magic[0] == 0x37 && magic[1] == 0x7a && magic[2] == (byte) 0xbc
                        && magic[3] == (byte) 0xaf && magic[4] == 0x27 && magic[5] == 0x1c) {
                    return SEVEN_Z;
                }
                if (magic.length >= 2 && magic[0] == 0x1f && magic[1] == (byte) 0x8b) {
                    return GZIP;
                }
                if (magic.length >= 7
                        && magic[0] == 0x52 && magic[1] == 0x61 && magic[2] == 0x72 && magic[3] == 0x21
                        && magic[4] == 0x1a && magic[5] == 0x07) {
                    return RAR;
                }
            } catch (IOException ignored) {
                // 格式识别失败交给后续错误处理。
            }
            return null;
        }
    }
}
