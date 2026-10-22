package cn.rvport.backend.archive;

import java.util.UUID;

public record ArchiveArtifactRef(
        String format,
        UUID storedArtifactId,
        String artifactType,
        String contentType,
        String filename
) {
}
