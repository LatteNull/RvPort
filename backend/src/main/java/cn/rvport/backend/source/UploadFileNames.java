package cn.rvport.backend.source;

import cn.rvport.backend.common.error.ApiException;
import org.springframework.http.HttpStatus;

public final class UploadFileNames {

    private UploadFileNames() {
    }

    public static String safeDisplayName(String originalFilename) {
        if (originalFilename == null || originalFilename.isBlank()) {
            return "source-archive";
        }
        String normalized = originalFilename.replace('\\', '/');
        int lastSlash = normalized.lastIndexOf('/');
        String name = lastSlash >= 0 ? normalized.substring(lastSlash + 1) : normalized;
        name = name.replaceAll("[^A-Za-z0-9._-]", "_");
        if (name.isBlank() || name.equals(".") || name.equals("..")) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "SOURCE_ARCHIVE_INVALID", "源码包文件名无效");
        }
        return name;
    }
}
