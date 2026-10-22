package cn.rvport.backend.source.archive;

import java.nio.file.Path;

public record SourceArchiveExtraction(
        Path workingCopyPath,
        int fileCount
) {
}
