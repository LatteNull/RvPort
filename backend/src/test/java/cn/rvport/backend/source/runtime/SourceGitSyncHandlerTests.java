package cn.rvport.backend.source.runtime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.task.RvPortTaskTypes;
import cn.rvport.backend.worker.TaskExecutionContext;
import cn.rvport.backend.worker.TaskHandlerResult;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class SourceGitSyncHandlerTests {

    @Mock
    private SourceFetchRuntimeService sourceFetchRuntimeService;

    @Mock
    private TaskExecutionContext context;

    @Test
    void handlesSourceGitSyncTask() {
        SourceGitSyncInput input = new SourceGitSyncInput(
                UUID.randomUUID(),
                UUID.randomUUID(),
                "https://example.com/repo.git",
                "main",
                null,
                null,
                null,
                null,
                true
        );
        when(context.input(SourceGitSyncInput.class)).thenReturn(input);
        SourceGitSyncHandler handler = new SourceGitSyncHandler(sourceFetchRuntimeService);

        TaskHandlerResult result = handler.handle(context);

        assertThat(handler.taskType()).isEqualTo(RvPortTaskTypes.SOURCE_GIT_SYNC);
        assertThat(result.message()).isEqualTo("Git 源码同步成功");
        verify(sourceFetchRuntimeService).sync(input, context);
    }

    @Test
    void propagatesSourceFetchFailure() {
        SourceGitSyncInput input = new SourceGitSyncInput(
                UUID.randomUUID(), UUID.randomUUID(), "https://example.com/repo", null,
                null, null, null, null, false);
        when(context.input(SourceGitSyncInput.class)).thenReturn(input);
        RuntimeException failure = new RuntimeException("clone failed");
        org.mockito.Mockito.doThrow(failure).when(sourceFetchRuntimeService).sync(input, context);

        assertThatThrownBy(() -> new SourceGitSyncHandler(sourceFetchRuntimeService).handle(context))
                .isSameAs(failure);
    }
}
