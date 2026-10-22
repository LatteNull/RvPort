package cn.rvport.backend.task;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.project.ProjectAccessService;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.jooq.JSONB;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpStatus;

@ExtendWith(MockitoExtension.class)
class ScriptExecutionServiceTests {

    @Mock private ScriptExecutionRepository repository;
    @Mock private ProjectAccessService projectAccessService;
    private ScriptExecutionService service;

    @BeforeEach
    void setUp() {
        service = new ScriptExecutionService(repository, projectAccessService, new ObjectMapper());
    }

    @Test
    void listsExecutionsWithNormalizedPaginationAndMappedStatus() {
        UUID projectId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        ScriptExecutionListRequest request = new ScriptExecutionListRequest(null, null, null, null, null, null);
        ScriptExecutionRepository.Row row = row(projectId, TaskStatus.RUNNING);
        when(repository.count(projectId, request)).thenReturn(1L);
        when(repository.list(projectId, request)).thenReturn(List.of(row));

        var page = service.list(projectId, request, actorId, false);

        assertThat(page.page()).isEqualTo(1);
        assertThat(page.pageSize()).isEqualTo(20);
        assertThat(page.items()).singleElement().satisfies(item -> {
            assertThat(item.id()).isEqualTo(row.taskId());
            assertThat(item.status()).isEqualTo(ScriptExecutionStatus.RUNNING);
            assertThat(item.environmentName()).isEqualTo("target");
        });
        verify(projectAccessService).requireProjectAccess(projectId, actorId, false);
    }

    @Test
    void getsDetailAndRemovesAllSensitiveSummaryFields() {
        UUID projectId = UUID.randomUUID();
        ScriptExecutionRepository.Row row = row(projectId, TaskStatus.SUCCEEDED);
        JSONB summary = JSONB.valueOf("""
                {"result":"ok","script":"secret","password":"p","privateKey":"k","passphrase":"x","secret":"s"}
                """);
        when(repository.findDetail(row.taskId())).thenReturn(Optional.of(
                new ScriptExecutionRepository.DetailRow(row, UUID.randomUUID(), "CUSTOM_BASH", summary)));

        ScriptExecutionDetailResponse response = service.get(row.taskId(), UUID.randomUUID(), true);

        assertThat(response.summary()).containsOnlyKeys("result").containsEntry("result", "ok");
        assertThat(response.status()).isEqualTo(ScriptExecutionStatus.SUCCEEDED);
    }

    @Test
    void detailUsesEmptySummaryForNullBlankOrMalformedJson() {
        UUID projectId = UUID.randomUUID();
        ScriptExecutionRepository.Row row = row(projectId, TaskStatus.FAILED);
        when(repository.findDetail(row.taskId())).thenReturn(
                Optional.of(new ScriptExecutionRepository.DetailRow(row, null, null, null)),
                Optional.of(new ScriptExecutionRepository.DetailRow(row, null, null, JSONB.valueOf(" "))),
                Optional.of(new ScriptExecutionRepository.DetailRow(row, null, null, JSONB.valueOf("not-json"))));

        assertThat(service.get(row.taskId(), UUID.randomUUID(), false).summary()).isEmpty();
        assertThat(service.get(row.taskId(), UUID.randomUUID(), false).summary()).isEmpty();
        assertThat(service.get(row.taskId(), UUID.randomUUID(), false).summary()).isEmpty();
    }

    @Test
    void rejectsMissingExecutionAfterCheckingTaskAccess() {
        UUID taskId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        when(repository.findDetail(taskId)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.get(taskId, actorId, false))
                .isInstanceOfSatisfying(ApiException.class, ex -> {
                    assertThat(ex.status()).isEqualTo(HttpStatus.NOT_FOUND);
                    assertThat(ex.code()).isEqualTo("SCRIPT_EXECUTION_NOT_FOUND");
                });
        verify(projectAccessService).requireTaskAccess(taskId, actorId, false);
    }

    private ScriptExecutionRepository.Row row(UUID projectId, TaskStatus status) {
        return new ScriptExecutionRepository.Row(
                UUID.randomUUID(), projectId, UUID.randomUUID(), "target", status, 50, "running", "sha", 12,
                status == TaskStatus.RUNNING ? null : 0, 4, OffsetDateTime.now(), OffsetDateTime.now(),
                status == TaskStatus.RUNNING ? null : OffsetDateTime.now());
    }
}
