package cn.rvport.backend.archive;

import org.springframework.core.io.Resource;

public record ProjectArchiveDownload(
        Resource resource,
        String filename,
        String contentType
) {
}
