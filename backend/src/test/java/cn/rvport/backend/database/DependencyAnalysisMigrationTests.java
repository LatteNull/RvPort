package cn.rvport.backend.database;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;

class DependencyAnalysisMigrationTests {

    @Test
    void providerVersionMigrationAddsDisplayFieldsConstraintsAndIndexes() throws Exception {
        String sql = new String(
                new ClassPathResource("db/changelog/changes/0110-dependency-analysis-provider-version-fields.sql")
                        .getInputStream()
                        .readAllBytes(),
                StandardCharsets.UTF_8
        ).toLowerCase();

        assertThat(sql).contains("source_provider_package text");
        assertThat(sql).contains("source_provider_version text");
        assertThat(sql).contains("source_detected_version text");
        assertThat(sql).contains("target_provider_package text");
        assertThat(sql).contains("target_provider_version text");
        assertThat(sql).contains("target_detected_version text");
        assertThat(sql).contains("provider_version_status text");
        assertThat(sql).contains("version_evidence_confidence text");

        assertThat(sql).contains("provider_version_status in");
        assertThat(sql).contains("'same_major'");
        assertThat(sql).contains("'target_newer'");
        assertThat(sql).contains("'target_older'");
        assertThat(sql).contains("'target_package_available_source_unowned'");
        assertThat(sql).contains("'no_target_version_found'");
        assertThat(sql).contains("'unknown'");

        assertThat(sql).contains("version_evidence_confidence in");
        assertThat(sql).contains("'package_owner'");
        assertThat(sql).contains("'command_version'");
        assertThat(sql).contains("'elf_metadata'");
        assertThat(sql).contains("'filename'");
        assertThat(sql).contains("'strings'");

        assertThat(sql).contains("dependency_analysis_items_project_revision_provider_status_idx");
        assertThat(sql).contains("dependency_analysis_items_project_revision_source_provider_idx");
        assertThat(sql).contains("dependency_analysis_items_project_revision_target_provider_idx");
    }
}
