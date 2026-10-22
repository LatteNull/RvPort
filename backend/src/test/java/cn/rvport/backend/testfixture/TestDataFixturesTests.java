package cn.rvport.backend.testfixture;

import static org.assertj.core.api.Assertions.assertThat;

import cn.rvport.backend.environment.EnvironmentStatus;
import cn.rvport.backend.project.ProjectStatus;
import cn.rvport.backend.task.TaskStatus;
import org.junit.jupiter.api.Test;

class TestDataFixturesTests {

    @Test
    void createsConsistentDomainGraph() {
        assertThat(TestDataFixtures.project().id()).isEqualTo(TestDataFixtures.PROJECT_ID);
        assertThat(TestDataFixtures.project().status()).isEqualTo(ProjectStatus.ACTIVE);
        assertThat(TestDataFixtures.task().projectId()).isEqualTo(TestDataFixtures.PROJECT_ID);
        assertThat(TestDataFixtures.task().status()).isEqualTo(TaskStatus.RUNNING);
        assertThat(TestDataFixtures.environment().projectId()).isEqualTo(TestDataFixtures.PROJECT_ID);
        assertThat(TestDataFixtures.environment().status()).isEqualTo(EnvironmentStatus.AVAILABLE);
        assertThat(TestDataFixtures.sourceRevision().projectId()).isEqualTo(TestDataFixtures.PROJECT_ID);
        assertThat(TestDataFixtures.artifact().taskId()).isEqualTo(TestDataFixtures.TASK_ID);
    }
}
