package cn.rvport.backend.artifact;

import org.springframework.core.io.Resource;

public record StoredArtifactResource(
        StoredArtifactView artifact,
        Resource resource
) {
}
