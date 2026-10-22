package cn.rvport.backend.database;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;

class ModelProfileMigrationTests {

    @Test
    void migrationDefinesModelProfilesAndStageAssignments() throws Exception {
        String sql = new String(
                new ClassPathResource("db/changelog/changes/0099-model-profiles.sql")
                        .getInputStream()
                        .readAllBytes(),
                StandardCharsets.UTF_8
        ).toLowerCase();

        assertThat(sql).contains("create table if not exists model_profiles");
        assertThat(sql).contains("api_key_encrypted text");
        assertThat(sql).contains("model_profiles_name_uidx");
        assertThat(sql).contains("model_profiles_enabled_idx");
        assertThat(sql).contains("model_profiles_last_tested_at_idx");
        assertThat(sql).contains("create table if not exists model_stage_assignments");
        assertThat(sql).contains("stage in ('test_log_compare')");
        assertThat(sql).contains("model_stage_assignments_profile_idx");
        assertThat(sql).contains("insert into model_profiles");
        assertThat(sql).contains("namespace = 'codex-provider'");
    }

    @Test
    void migrationDefinesAgentRuntimesAndStageRuntimeBinding() throws Exception {
        String sql = new String(
                new ClassPathResource("db/changelog/changes/0106-agent-runtime-selection.sql")
                        .getInputStream()
                        .readAllBytes(),
                StandardCharsets.UTF_8
        ).toLowerCase();

        assertThat(sql).contains("create table if not exists agent_runtimes");
        assertThat(sql).contains("agent_type in ('codex', 'deepseek_harness', 'opencode')");
        assertThat(sql).contains("agent_runtimes_type_uidx");
        assertThat(sql).contains("agent_runtimes_enabled_idx");
        assertThat(sql).contains("insert into agent_runtimes");
        assertThat(sql).contains("add column if not exists agent_runtime_id uuid");
        assertThat(sql).contains("model_stage_assignments_agent_runtime_fk");
        assertThat(sql).contains("model_stage_assignments_agent_runtime_idx");
    }

    @Test
    void migrationDefinesModelProfileAgentProbeFlow() throws Exception {
        String sql = new String(
                new ClassPathResource("db/changelog/changes/0115-model-profile-agent-probe-flow.sql")
                        .getInputStream()
                        .readAllBytes(),
                StandardCharsets.UTF_8
        ).toLowerCase();

        assertThat(sql).contains("last_connectivity_status");
        assertThat(sql).contains("model_profiles_connectivity_status_chk");
        assertThat(sql).contains("create table if not exists model_profile_agent_probe_runs");
        assertThat(sql).contains("create table if not exists model_profile_agent_probe_results");
        assertThat(sql).contains("model_profile_agent_probe_runs_profile_active_idx");
        assertThat(sql).contains("model_profile_agent_probe_results_profile_runtime_created_idx");
        assertThat(sql).contains("pending");
        assertThat(sql).contains("running");
        assertThat(sql).contains("partial_success");
    }

    @Test
    void migrationRemovesStageCompatibilityColumnsWithoutDroppingGenericHistory() throws Exception {
        String sql = new String(
                new ClassPathResource("db/changelog/changes/0124-decouple-model-agent-compatibility.sql")
                        .getInputStream()
                        .readAllBytes(),
                StandardCharsets.UTF_8
        ).toLowerCase();

        assertThat(sql).contains("drop column if exists last_test_compare_compatible");
        assertThat(sql).contains("drop column if exists test_log_compare_compatible");
        assertThat(sql).contains("drop column if exists kb_ai_extension_compatible");
        assertThat(sql).doesNotContain("drop table", "model_stage_assignments;");
    }
}
