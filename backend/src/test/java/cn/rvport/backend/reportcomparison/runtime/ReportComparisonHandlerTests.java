package cn.rvport.backend.reportcomparison.runtime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.reportcomparison.ReportComparisonTaskInput;
import cn.rvport.backend.task.RvPortTaskTypes;
import cn.rvport.backend.worker.TaskExecutionContext;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

class ReportComparisonHandlerTests {

    @Test
    void exposesTaskTypeAndDelegatesInput() {
        ReportComparisonRuntimeService service = Mockito.mock(ReportComparisonRuntimeService.class);
        TaskExecutionContext context = Mockito.mock(TaskExecutionContext.class);
        ReportComparisonTaskInput input = new ReportComparisonTaskInput(
                UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID());
        when(context.input(ReportComparisonTaskInput.class)).thenReturn(input);
        ReportComparisonHandler handler = new ReportComparisonHandler(service);

        assertThat(handler.taskType()).isEqualTo(RvPortTaskTypes.REPORT_COMPARE);
        assertThat(handler.handle(context).message()).isEqualTo("报告对比完成");
        verify(service).run(input, context);
    }

    @Test
    void propagatesRuntimeFailure() {
        ReportComparisonRuntimeService service = Mockito.mock(ReportComparisonRuntimeService.class);
        TaskExecutionContext context = Mockito.mock(TaskExecutionContext.class);
        ReportComparisonTaskInput input = new ReportComparisonTaskInput(
                UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID());
        when(context.input(ReportComparisonTaskInput.class)).thenReturn(input);
        RuntimeException failure = new RuntimeException("failed");
        org.mockito.Mockito.doThrow(failure).when(service).run(input, context);

        assertThatThrownBy(() -> new ReportComparisonHandler(service).handle(context)).isSameAs(failure);
    }
}
