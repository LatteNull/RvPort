package cn.rvport.backend.automatedtest;

import static org.assertj.core.api.Assertions.assertThat;

import cn.rvport.backend.jooq.tables.records.TestRunsRecord;
import cn.rvport.backend.task.TaskStatus;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class AutomatedTestRunViewTests {

    @Test
    void mapsPresentAndMissingBatchRolesFromDatabaseRecord() {
        TestRunsRecord record = record();
        record.setTestBatchRole(TestBatchRole.SOURCE.name());
        assertThat(AutomatedTestRunView.from(record).testBatchRole()).isEqualTo(TestBatchRole.SOURCE);

        record.setTestBatchRole(null);
        assertThat(AutomatedTestRunView.from(record).testBatchRole()).isNull();
    }

    private TestRunsRecord record() {
        TestRunsRecord record = new TestRunsRecord();
        record.setId(UUID.randomUUID());
        record.setProjectId(UUID.randomUUID());
        record.setTaskId(UUID.randomUUID());
        record.setBuildRunId(UUID.randomUUID());
        record.setSourceRevisionId(UUID.randomUUID());
        record.setEnvironmentId(UUID.randomUUID());
        record.setStatus(TaskStatus.SUCCEEDED.name());
        return record;
    }
}
