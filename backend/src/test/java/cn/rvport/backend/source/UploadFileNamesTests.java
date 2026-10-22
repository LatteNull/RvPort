package cn.rvport.backend.source;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import cn.rvport.backend.common.error.ApiException;
import org.junit.jupiter.api.Test;

class UploadFileNamesTests {

    @Test
    void keepsNormalArchiveName() {
        assertThat(UploadFileNames.safeDisplayName("source.tar.gz")).isEqualTo("source.tar.gz");
    }

    @Test
    void stripsPathTraversalSegments() {
        assertThat(UploadFileNames.safeDisplayName("../source.zip")).isEqualTo("source.zip");
    }

    @Test
    void rejectsInvalidEdgeCaseName() {
        assertThat(UploadFileNames.safeDisplayName(null)).isEqualTo("source-archive");
        assertThat(UploadFileNames.safeDisplayName("  ")).isEqualTo("source-archive");
        assertThat(UploadFileNames.safeDisplayName("C:\\uploads\\source 1.zip")).isEqualTo("source_1.zip");
        assertThatThrownBy(() -> UploadFileNames.safeDisplayName("."))
                .isInstanceOf(ApiException.class);
        assertThatThrownBy(() -> UploadFileNames.safeDisplayName("folder/"))
                .isInstanceOf(ApiException.class);
        assertThatThrownBy(() -> UploadFileNames.safeDisplayName(".."))
                .isInstanceOf(ApiException.class);
    }
}
