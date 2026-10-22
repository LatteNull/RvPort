package cn.rvport.backend.source.archive;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.zip.GZIPOutputStream;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;
import org.apache.commons.compress.archivers.sevenz.SevenZArchiveEntry;
import org.apache.commons.compress.archivers.sevenz.SevenZOutputFile;
import org.apache.commons.compress.archivers.tar.TarArchiveEntry;
import org.apache.commons.compress.archivers.tar.TarArchiveOutputStream;
import org.apache.commons.compress.compressors.xz.XZCompressorOutputStream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class SourceArchiveExtractorTests {

    @TempDir
    private Path tempDir;

    private final SourceArchiveExtractor extractor = new SourceArchiveExtractor();

    @Test
    void extractsZipIntoWorkingCopyDirectory() throws Exception {
        Path archive = tempDir.resolve("source.zip");
        writeZip(archive, "demo/README.md", "hello");
        Path target = tempDir.resolve("work");

        SourceArchiveExtraction result = extractor.extract(archive, "source.zip", target);

        assertThat(result.fileCount()).isEqualTo(1);
        assertThat(result.workingCopyPath()).isEqualTo(target.toAbsolutePath().normalize());
        assertThat(target.resolve("demo/README.md")).hasContent("hello");
    }

    @Test
    void rejectsZipSlipEntry() throws Exception {
        Path archive = tempDir.resolve("source.zip");
        writeZip(archive, "../escape.txt", "bad");

        assertThatThrownBy(() -> extractor.extract(archive, "source.zip", tempDir.resolve("work")))
                .isInstanceOf(SourceArchiveException.class)
                .extracting("code")
                .isEqualTo(SourceArchiveErrorCode.SOURCE_ARCHIVE_UNSAFE_PATH);
    }

    @Test
    void rejectsEmptyZip() throws Exception {
        Path archive = tempDir.resolve("empty.zip");
        try (ZipOutputStream zip = new ZipOutputStream(Files.newOutputStream(archive))) {
            zip.putNextEntry(new ZipEntry("empty/"));
            zip.closeEntry();
        }

        assertThatThrownBy(() -> extractor.extract(archive, "empty.zip", tempDir.resolve("work")))
                .isInstanceOf(SourceArchiveException.class)
                .extracting("code")
                .isEqualTo(SourceArchiveErrorCode.SOURCE_ARCHIVE_EMPTY);
    }

    @Test
    void extractsSingleFileGzipWhenFilenameIsUsable() throws Exception {
        Path archive = tempDir.resolve("main.c.gz");
        try (GZIPOutputStream gzip = new GZIPOutputStream(Files.newOutputStream(archive))) {
            gzip.write("int main() { return 0; }".getBytes());
        }

        SourceArchiveExtraction result = extractor.extract(archive, "main.c.gz", tempDir.resolve("work"));

        assertThat(result.fileCount()).isEqualTo(1);
        assertThat(tempDir.resolve("work/main.c")).hasContent("int main() { return 0; }");
    }

    @Test
    void rejectsUnsupportedFormat() throws Exception {
        Path archive = tempDir.resolve("source.bin");
        Files.writeString(archive, "demo");

        assertThatThrownBy(() -> extractor.extract(archive, "source.bin", tempDir.resolve("work")))
                .isInstanceOf(SourceArchiveException.class)
                .extracting("code")
                .isEqualTo(SourceArchiveErrorCode.SOURCE_ARCHIVE_UNSUPPORTED_FORMAT);
    }

    @Test
    void extractsTarGzTgzAndTarXzArchives() throws Exception {
        Path tarGz = tempDir.resolve("source.tar.gz");
        writeTar(tarGz, false, "src/main.c", "tar-gz");
        assertThat(extractor.extract(tarGz, "SOURCE.TAR.GZ", tempDir.resolve("tar-gz")).fileCount()).isEqualTo(1);
        assertThat(tempDir.resolve("tar-gz/src/main.c")).hasContent("tar-gz");

        Path tgz = tempDir.resolve("source.tgz");
        writeTar(tgz, false, "src/main.c", "tgz");
        assertThat(extractor.extract(tgz, "source.tgz", tempDir.resolve("tgz")).fileCount()).isEqualTo(1);

        Path tarXz = tempDir.resolve("source.tar.xz");
        writeTar(tarXz, true, "src/main.c", "tar-xz");
        assertThat(extractor.extract(tarXz, "source.tar.xz", tempDir.resolve("tar-xz")).fileCount()).isEqualTo(1);
        assertThat(tempDir.resolve("tar-xz/src/main.c")).hasContent("tar-xz");
    }

    @Test
    void extractsSevenZipWithDirectoriesAndGzipSuffixVariants() throws Exception {
        Path seven = tempDir.resolve("source.7z");
        try (SevenZOutputFile output = new SevenZOutputFile(seven.toFile())) {
            SevenZArchiveEntry directory = output.createArchiveEntry(tempDir.toFile(), "src/");
            directory.setDirectory(true);
            output.putArchiveEntry(directory);
            output.closeArchiveEntry();
            byte[] content = "seven".getBytes();
            SevenZArchiveEntry file = new SevenZArchiveEntry();
            file.setName("src/main.c");
            file.setSize(content.length);
            output.putArchiveEntry(file);
            output.write(content);
            output.closeArchiveEntry();
        }
        assertThat(extractor.extract(seven, "source.7z", tempDir.resolve("seven")).fileCount()).isEqualTo(1);
        assertThat(tempDir.resolve("seven/src/main.c")).hasContent("seven");

        Path gzip = tempDir.resolve("README.gzip");
        writeGzip(gzip, "gzip");
        assertThat(extractor.extract(gzip, "README.GZIP", tempDir.resolve("gzip")).fileCount()).isEqualTo(1);
        assertThat(tempDir.resolve("gzip/README")).hasContent("gzip");
    }

    @Test
    void detectsZipAndGzipByMagicWhenExtensionIsUnknown() throws Exception {
        Path zip = tempDir.resolve("archive.data");
        writeZip(zip, "README", "magic-zip");
        assertThat(extractor.extract(zip, null, tempDir.resolve("magic-zip")).fileCount()).isEqualTo(1);

        Path gzip = tempDir.resolve("payload.data");
        writeGzip(gzip, "magic-gzip");
        assertThatThrownBy(() -> extractor.extract(gzip, "payload.data", tempDir.resolve("magic-gzip")))
                .isInstanceOf(SourceArchiveException.class)
                .extracting("code").isEqualTo(SourceArchiveErrorCode.SOURCE_ARCHIVE_UNSUPPORTED_STRUCTURE);
    }

    @Test
    void recognizesDamagedSevenZipAndRarByExtensionAndMagic() throws Exception {
        Path brokenSeven = tempDir.resolve("broken.7z");
        Files.write(brokenSeven, new byte[]{0x37, 0x7a, (byte) 0xbc, (byte) 0xaf, 0x27, 0x1c, 0, 0});
        assertUnsupportedStructure(brokenSeven, "broken.7z", "seven-extension");
        assertUnsupportedStructure(brokenSeven, "broken.data", "seven-magic");

        Path brokenRar = tempDir.resolve("broken.rar");
        Files.write(brokenRar, new byte[]{0x52, 0x61, 0x72, 0x21, 0x1a, 0x07, 0, 0});
        assertArchiveError(brokenRar, "broken.rar", "rar-extension", SourceArchiveErrorCode.SOURCE_ARCHIVE_EMPTY);
        assertArchiveError(brokenRar, "broken.data", "rar-magic", SourceArchiveErrorCode.SOURCE_ARCHIVE_EMPTY);
    }

    @Test
    void rejectsAbsoluteWindowsAndBlankArchivePathsAndCleansExistingTarget() throws Exception {
        Path unix = tempDir.resolve("unix.zip");
        writeZip(unix, "/absolute.txt", "bad");
        assertUnsafe(unix, "unix");

        Path windows = tempDir.resolve("windows.zip");
        writeZip(windows, "C:\\absolute.txt", "bad");
        assertUnsafe(windows, "windows");

        Path target = tempDir.resolve("replace");
        Files.createDirectories(target);
        Files.writeString(target.resolve("old.txt"), "old");
        Path valid = tempDir.resolve("valid.zip");
        writeZip(valid, "new.txt", "new");
        extractor.extract(valid, "valid.zip", target);
        assertThat(target.resolve("old.txt")).doesNotExist();
        assertThat(target.resolve("new.txt")).hasContent("new");
    }

    @Test
    void rejectsTarNamedGzipMissingFilesAndEmptyGzip() throws Exception {
        Path gzip = tempDir.resolve("source.tar.gz");
        writeGzip(gzip, "not-tar");
        assertThat(extractor.extract(gzip, "source.gz", tempDir.resolve("gzip-name")).fileCount()).isEqualTo(1);
        assertThat(tempDir.resolve("gzip-name/source")).hasContent("not-tar");

        Path empty = tempDir.resolve("empty.gz");
        writeGzip(empty, "");
        assertThatThrownBy(() -> extractor.extract(empty, "empty.gz", tempDir.resolve("empty-gzip")))
                .isInstanceOf(SourceArchiveException.class)
                .extracting("code").isEqualTo(SourceArchiveErrorCode.SOURCE_ARCHIVE_EMPTY);

        Path missing = tempDir.resolve("missing.bin");
        assertThatThrownBy(() -> extractor.extract(missing, "missing.bin", tempDir.resolve("missing")))
                .isInstanceOf(SourceArchiveException.class)
                .extracting("code").isEqualTo(SourceArchiveErrorCode.SOURCE_ARCHIVE_UNSUPPORTED_FORMAT);
    }

    @Test
    void rejectsTruncatedAndNearMissMagicSignatures() throws Exception {
        List<byte[]> invalidSignatures = new java.util.ArrayList<>();
        invalidSignatures.add(new byte[0]);
        invalidSignatures.add(new byte[]{0x50});
        invalidSignatures.add(new byte[]{0x50, 0, 0, 0});
        invalidSignatures.add(new byte[]{0, 0x4b, 0, 0});
        addMutations(invalidSignatures, new byte[]{0x37, 0x7a, (byte) 0xbc, (byte) 0xaf, 0x27, 0x1c});
        addMutations(invalidSignatures, new byte[]{0x1f, (byte) 0x8b});
        addMutations(invalidSignatures, new byte[]{0x52, 0x61, 0x72, 0x21, 0x1a, 0x07, 0});

        int index = 0;
        for (byte[] signature : invalidSignatures) {
            Path archive = tempDir.resolve("near-miss-" + index + ".data");
            Files.write(archive, signature);
            int current = index++;
            assertThatThrownBy(() -> extractor.extract(archive, "unknown.data", tempDir.resolve("near-" + current)))
                    .isInstanceOf(SourceArchiveException.class)
                    .extracting("code").isEqualTo(SourceArchiveErrorCode.SOURCE_ARCHIVE_UNSUPPORTED_FORMAT);
        }
    }

    @Test
    void rejectsBlankEntryAndMissingGzipOutputNames() throws Exception {
        Path blankEntry = tempDir.resolve("blank.zip");
        writeZip(blankEntry, " ", "bad");
        assertUnsafe(blankEntry, "blank-entry");

        Path gzip = tempDir.resolve("payload.data");
        writeGzip(gzip, "payload");
        assertArchiveError(gzip, null, "gzip-null-name", SourceArchiveErrorCode.SOURCE_ARCHIVE_UNSUPPORTED_STRUCTURE);
        assertArchiveError(gzip, " ", "gzip-blank-name", SourceArchiveErrorCode.SOURCE_ARCHIVE_UNSUPPORTED_STRUCTURE);
    }

    private void writeZip(Path archive, String entryName, String content) throws IOException {
        try (ZipOutputStream zip = new ZipOutputStream(Files.newOutputStream(archive))) {
            zip.putNextEntry(new ZipEntry(entryName));
            zip.write(content.getBytes());
            zip.closeEntry();
        }
    }

    private void writeGzip(Path archive, String content) throws IOException {
        try (GZIPOutputStream gzip = new GZIPOutputStream(Files.newOutputStream(archive))) {
            gzip.write(content.getBytes());
        }
    }

    private void addMutations(List<byte[]> target, byte[] signature) {
        int comparedLength = signature.length == 7 ? 6 : signature.length;
        for (int i = 0; i < comparedLength; i++) {
            byte[] mutation = signature.clone();
            mutation[i] ^= 0x01;
            target.add(mutation);
        }
    }

    private void writeTar(Path archive, boolean xz, String entryName, String content) throws IOException {
        var file = Files.newOutputStream(archive);
        var compressed = xz ? new XZCompressorOutputStream(file) : new GZIPOutputStream(file);
        try (compressed; TarArchiveOutputStream tar = new TarArchiveOutputStream(compressed)) {
            TarArchiveEntry directory = new TarArchiveEntry("src/");
            tar.putArchiveEntry(directory);
            tar.closeArchiveEntry();
            byte[] bytes = content.getBytes();
            TarArchiveEntry entry = new TarArchiveEntry(entryName);
            entry.setSize(bytes.length);
            tar.putArchiveEntry(entry);
            tar.write(bytes);
            tar.closeArchiveEntry();
        }
    }

    private void assertUnsafe(Path archive, String targetName) {
        assertThatThrownBy(() -> extractor.extract(archive, archive.getFileName().toString(), tempDir.resolve(targetName)))
                .isInstanceOf(SourceArchiveException.class)
                .extracting("code").isEqualTo(SourceArchiveErrorCode.SOURCE_ARCHIVE_UNSAFE_PATH);
    }

    private void assertUnsupportedStructure(Path archive, String filename, String targetName) {
        assertArchiveError(archive, filename, targetName, SourceArchiveErrorCode.SOURCE_ARCHIVE_UNSUPPORTED_STRUCTURE);
    }

    private void assertArchiveError(Path archive, String filename, String targetName, SourceArchiveErrorCode code) {
        assertThatThrownBy(() -> extractor.extract(archive, filename, tempDir.resolve(targetName)))
                .isInstanceOf(SourceArchiveException.class)
                .extracting("code").isEqualTo(code);
    }
}
