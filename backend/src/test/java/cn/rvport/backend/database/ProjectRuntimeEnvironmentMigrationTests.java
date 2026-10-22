package cn.rvport.backend.database;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;

class ProjectRuntimeEnvironmentMigrationTests {

    @Test
    void migrationDefinesRuntimeEnvironmentTableAndVersionColumns() throws Exception {
        String sql = new String(
                new ClassPathResource("db/changelog/changes/0098-project-runtime-environments.sql")
                        .getInputStream()
                        .readAllBytes(),
                StandardCharsets.UTF_8
        );

        String normalized = sql.toLowerCase();

        assertThat(normalized).contains("create table if not exists project_runtime_environments");
        assertThat(normalized).contains("source_environment_id uuid");
        assertThat(normalized).contains("target_environment_id uuid");
        assertThat(normalized).contains("version bigint not null default 1");
        assertThat(normalized).contains("project_runtime_environments_distinct_chk");
        assertThat(normalized).contains("add column if not exists environment_config_version bigint");
        assertThat(normalized).contains("alter table source_deploy_runs");
        assertThat(normalized).contains("alter table build_runs");
        assertThat(normalized).contains("alter table test_runs");
        assertThat(normalized).contains("project_runtime_environments_source_idx");
        assertThat(normalized).contains("source_deploy_runs_revision_env_config_idx");
        assertThat(normalized).contains("build_runs_revision_env_config_idx");
    }
}
