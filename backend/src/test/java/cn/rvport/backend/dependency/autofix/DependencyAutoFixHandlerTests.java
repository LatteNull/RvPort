package cn.rvport.backend.dependency.autofix;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.dependency.DependencyAnalysisCreateRequest;
import cn.rvport.backend.dependency.DependencyAnalysisCreateResponse;
import cn.rvport.backend.dependency.DependencyAnalysisService;
import cn.rvport.backend.dependency.DependencyRiskLevel;
import cn.rvport.backend.dependency.DependencyTargetMatchStatus;
import cn.rvport.backend.environment.runtime.SshCommandResult;
import cn.rvport.backend.environment.runtime.SshRuntimeService;
import cn.rvport.backend.environment.runtime.SshRuntimeException;
import cn.rvport.backend.task.TaskErrorCode;
import cn.rvport.backend.task.TaskExecutionException;
import cn.rvport.backend.task.TaskResponse;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.task.TaskView;
import cn.rvport.backend.task.ToolRunRepository;
import cn.rvport.backend.worker.TaskCancelledException;
import cn.rvport.backend.worker.TaskExecutionContext;
import java.time.Duration;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class DependencyAutoFixHandlerTests {

    @Mock
    private DependencyAutoFixRepository repository;
    @Mock
    private SshRuntimeService sshRuntimeService;
    @Mock
    private DependencyAnalysisService dependencyAnalysisService;
    @Mock
    private ToolRunRepository toolRunRepository;
    @Mock
    private TaskExecutionContext context;

    @org.junit.jupiter.api.BeforeEach
    void allowPublication() {
        org.mockito.Mockito.lenient().when(context.publish(any())).thenAnswer(call -> ((java.util.function.Supplier<?>) call.getArgument(0)).get());
    }

    @Test
    void lostAttemptDuringInstallCannotWriteItemOrCreateRerun() {
        Fixtures fixtures = fixtures(true);
        DependencyAutoFixItemView item = item(fixtures.run.id(), "zlib-devel", "1.2.13-2", DependencyRiskLevel.MEDIUM, DependencyAutoFixItemStatus.PENDING);
        when(repository.listPendingItems(fixtures.run.id())).thenReturn(List.of(item));
        when(sshRuntimeService.executeRemote(any(), any(), eq(null), eq(false), any(), eq(context)))
                .thenThrow(new cn.rvport.backend.worker.TaskAttemptLostException());
        assertThatThrownBy(() -> handler().handle(context))
                .isInstanceOf(cn.rvport.backend.worker.TaskAttemptLostException.class);
        verify(repository, never()).markItemFinished(any(), any(), any(), any(), any());
        verify(repository, never()).markRunFinished(any(), any(), any(), any());
        verify(toolRunRepository, never()).finish(any(), any(), any(), any());
        org.mockito.Mockito.verifyNoInteractions(dependencyAnalysisService);
    }

    @Test
    void installsSelectedPackageAndCreatesDependencyAnalysisRerun() {
        Fixtures fixtures = fixtures(true);
        DependencyAutoFixItemView item = item(fixtures.run.id(), "zlib-devel", "1.2.13-2", DependencyRiskLevel.MEDIUM, DependencyAutoFixItemStatus.PENDING);
        DependencyAutoFixItemView succeeded = withStatus(item, DependencyAutoFixItemStatus.SUCCEEDED);
        UUID rerunId = UUID.randomUUID();
        UUID rerunTaskId = UUID.randomUUID();
        when(repository.listPendingItems(fixtures.run.id())).thenReturn(List.of(item));
        when(sshRuntimeService.executeRemote(any(), any(), eq(null), eq(false), any(), eq(context)))
                .thenReturn(new SshCommandResult(0, "installed", "", Duration.ofMillis(100)));
        when(repository.summaryCounts(fixtures.run.id())).thenReturn(summary(List.of(succeeded)));
        when(dependencyAnalysisService.create(eq(fixtures.run.projectId()), any(DependencyAnalysisCreateRequest.class),
                eq(fixtures.userId), eq(false), eq(null)))
                .thenReturn(new DependencyAnalysisCreateResponse(rerunId, rerunTaskId, fixtures.run.sourceRevisionId(),
                        UUID.randomUUID(), TaskResponse.from(task(rerunTaskId, fixtures.run.projectId(), fixtures.userId))));

        handler().handle(context);

        verify(repository).markItemFinished(eq(item.id()), eq(DependencyAutoFixItemStatus.SUCCEEDED), eq(0), eq(null), any());
        verify(repository).linkRerun(eq(fixtures.run.id()), eq(rerunId), eq(rerunTaskId), any(), eq(DependencyAutoFixRunStatus.SUCCEEDED));
        verify(toolRunRepository).finish(any(), eq(TaskStatus.SUCCEEDED), eq(0), any());

        ArgumentCaptor<String> commandCaptor = ArgumentCaptor.forClass(String.class);
        verify(sshRuntimeService).executeRemote(any(), commandCaptor.capture(), eq(null), eq(false), any(), eq(context));
        org.assertj.core.api.Assertions.assertThat(commandCaptor.getValue()).contains("pkg='zlib-devel'");
    }

    @Test
    void failsTaskAndDoesNotRerunWhenAllItemsFail() {
        Fixtures fixtures = fixtures(true);
        DependencyAutoFixItemView item = item(fixtures.run.id(), "missing-devel", "1", DependencyRiskLevel.MEDIUM, DependencyAutoFixItemStatus.PENDING);
        DependencyAutoFixItemView failed = withStatus(item, DependencyAutoFixItemStatus.FAILED);
        when(repository.listPendingItems(fixtures.run.id())).thenReturn(List.of(item));
        when(sshRuntimeService.executeRemote(any(), any(), eq(null), eq(false), any(), eq(context)))
                .thenReturn(new SshCommandResult(14, "", "install failed", Duration.ofMillis(50)));
        when(repository.summaryCounts(fixtures.run.id())).thenReturn(summary(List.of(failed)));

        assertThatThrownBy(() -> handler().handle(context))
                .isInstanceOf(TaskExecutionException.class)
                .extracting("errorCode")
                .isEqualTo("TASK_REMOTE_COMMAND_FAILED");

        verify(repository).markRunFinished(eq(fixtures.run.id()), eq(DependencyAutoFixRunStatus.FAILED), any(), any());
        verify(dependencyAnalysisService, never()).create(any(), any(), any(), anyBoolean(), any());
        verify(toolRunRepository).finish(any(), eq(TaskStatus.FAILED), eq(null), any());
    }

    @Test
    void keepsPartialStatusWhenSomeItemsAreUnavailable() {
        Fixtures fixtures = fixtures(false);
        DependencyAutoFixItemView first = item(fixtures.run.id(), "zlib-devel", "1", DependencyRiskLevel.MEDIUM, DependencyAutoFixItemStatus.PENDING);
        DependencyAutoFixItemView second = item(fixtures.run.id(), "gcc", "12", DependencyRiskLevel.HIGH, DependencyAutoFixItemStatus.PENDING);
        when(repository.listPendingItems(fixtures.run.id())).thenReturn(List.of(first, second));
        when(sshRuntimeService.executeRemote(any(), any(), eq(null), eq(false), any(), eq(context)))
                .thenReturn(
                        new SshCommandResult(0, "installed", "", Duration.ofMillis(30)),
                        new SshCommandResult(11, "RVPORT_AUTO_FIX_PACKAGE_UNAVAILABLE", "", Duration.ofMillis(30))
                );
        when(repository.summaryCounts(fixtures.run.id())).thenReturn(summary(List.of(
                withStatus(first, DependencyAutoFixItemStatus.SUCCEEDED),
                withStatus(second, DependencyAutoFixItemStatus.SKIPPED_UNAVAILABLE)
        )));

        handler().handle(context);

        verify(repository).markRunFinished(eq(fixtures.run.id()), eq(DependencyAutoFixRunStatus.PARTIALLY_SUCCEEDED), any(), eq(null));
        verify(dependencyAnalysisService, never()).create(any(), any(), any(), anyBoolean(), any());
        verify(toolRunRepository).finish(any(), eq(TaskStatus.SUCCEEDED), eq(0), any());
    }

    @Test
    void preservesInstallResultWhenRerunCreationFails() {
        Fixtures fixtures = fixtures(true);
        DependencyAutoFixItemView item = item(fixtures.run.id(), "zlib-devel", "1", DependencyRiskLevel.MEDIUM, DependencyAutoFixItemStatus.PENDING);
        when(repository.listPendingItems(fixtures.run.id())).thenReturn(List.of(item));
        when(sshRuntimeService.executeRemote(any(), any(), eq(null), eq(false), any(), eq(context)))
                .thenReturn(new SshCommandResult(10, "RVPORT_AUTO_FIX_ALREADY_SATISFIED", "", Duration.ofMillis(20)));
        when(repository.summaryCounts(fixtures.run.id()))
                .thenReturn(summary(List.of(withStatus(item, DependencyAutoFixItemStatus.SKIPPED_ALREADY_SATISFIED))));
        when(dependencyAnalysisService.create(any(), any(), any(), anyBoolean(), any()))
                .thenThrow(new IllegalStateException("queue down"));

        handler().handle(context);

        verify(repository).markRunFinished(eq(fixtures.run.id()), eq(DependencyAutoFixRunStatus.SUCCEEDED_WITH_REANALYSIS_FAILED),
                any(), eq("依赖安装完成，但重新创建依赖分析失败"));
        verify(toolRunRepository).finish(any(), eq(TaskStatus.SUCCEEDED), eq(0), any());
    }

    @Test
    void rejectsMissingAutoFixRunBeforeCreatingToolRun() {
        UUID runId = UUID.randomUUID();
        when(context.input(DependencyAutoFixTaskInput.class)).thenReturn(new DependencyAutoFixTaskInput(
                UUID.randomUUID(), runId, UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), 1L, false));
        when(repository.findRun(runId)).thenReturn(java.util.Optional.empty());

        assertThatThrownBy(() -> handler().handle(context))
                .isInstanceOf(TaskExecutionException.class)
                .extracting(ex -> ((TaskExecutionException) ex).errorCode())
                .isEqualTo(TaskErrorCode.RESOURCE_NOT_FOUND);
        verify(toolRunRepository, never()).create(any(), any(), any(), any(), any(), any(), any());
    }

    @Test
    void marksUnsafePackageItemFailedAndContinuesToRunSummary() {
        Fixtures fixtures = fixtures(false);
        DependencyAutoFixItemView item = item(fixtures.run.id(), "bad package", "1", DependencyRiskLevel.MEDIUM,
                DependencyAutoFixItemStatus.PENDING);
        when(repository.listPendingItems(fixtures.run.id())).thenReturn(List.of(item));
        when(repository.summaryCounts(fixtures.run.id())).thenReturn(summary(List.of(
                withStatus(item, DependencyAutoFixItemStatus.FAILED))));

        assertThatThrownBy(() -> handler().handle(context)).isInstanceOf(TaskExecutionException.class);

        verify(repository).markItemFinished(eq(item.id()), eq(DependencyAutoFixItemStatus.FAILED), eq(null),
                eq("软件包名称不安全或为空"), eq(Map.of("validation", "package-name-or-version")));
        verify(sshRuntimeService, never()).executeRemote(any(), any(), any(), anyBoolean(), any(), any());
    }

    @Test
    void recordsSanitizedSshFailureForItem() {
        Fixtures fixtures = fixtures(false);
        DependencyAutoFixItemView item = item(fixtures.run.id(), "zlib-devel", null, DependencyRiskLevel.MEDIUM,
                DependencyAutoFixItemStatus.PENDING);
        when(repository.listPendingItems(fixtures.run.id())).thenReturn(List.of(item));
        when(sshRuntimeService.executeRemote(any(), any(), eq(null), eq(false), any(), eq(context)))
                .thenThrow(new SshRuntimeException("password=secret\nnetwork down"));
        when(repository.summaryCounts(fixtures.run.id())).thenReturn(summary(List.of(
                withStatus(item, DependencyAutoFixItemStatus.FAILED))));

        assertThatThrownBy(() -> handler().handle(context)).isInstanceOf(TaskExecutionException.class);

        verify(repository).markItemFinished(eq(item.id()), eq(DependencyAutoFixItemStatus.FAILED), eq(null),
                eq("依赖安装 SSH 执行失败"), eq(Map.of("sshError", "password=**** network down")));
    }

    @Test
    void cancelsPendingItemsAndRunWhenCancellationIsRequested() {
        Fixtures fixtures = fixtures(false);
        DependencyAutoFixItemView item = item(fixtures.run.id(), "zlib-devel", "1", DependencyRiskLevel.MEDIUM,
                DependencyAutoFixItemStatus.PENDING);
        when(repository.listPendingItems(fixtures.run.id())).thenReturn(List.of(item));
        org.mockito.Mockito.doThrow(new TaskCancelledException("cancelled"))
                .when(context).throwIfCancellationRequested();

        assertThatThrownBy(() -> handler().handle(context)).isInstanceOf(TaskCancelledException.class);

        verify(repository).cancelPendingItems(fixtures.run.id());
        verify(repository).markRunFinished(fixtures.run.id(), DependencyAutoFixRunStatus.CANCELLED,
                Map.of("error", "任务已取消"), "任务已取消");
        verify(toolRunRepository).finish(any(), eq(TaskStatus.CANCELLED), eq(null), any());
    }

    @Test
    void convertsUnexpectedRepositoryFailure() {
        Fixtures fixtures = fixtures(false);
        when(repository.listPendingItems(fixtures.run.id())).thenThrow(new IllegalStateException("database down"));

        assertThatThrownBy(() -> handler().handle(context))
                .isInstanceOf(TaskExecutionException.class)
                .extracting(ex -> ((TaskExecutionException) ex).errorCode())
                .isEqualTo(TaskErrorCode.HANDLER_FAILED);
        verify(repository).markRunFinished(fixtures.run.id(), DependencyAutoFixRunStatus.FAILED,
                Map.of("error", "依赖自动修复失败"), "依赖自动修复失败");
        verify(toolRunRepository).finish(any(), eq(TaskStatus.FAILED), eq(null), any());
    }

    @Test
    void mapsEveryInstallResultAndFinalRunSummaryBoundary() {
        DependencyAutoFixHandler handler = handler();
        assertThatStatus(handler, result(0, null, null), DependencyAutoFixItemStatus.SUCCEEDED);
        assertThatStatus(handler, result(10, null, null), DependencyAutoFixItemStatus.SKIPPED_ALREADY_SATISFIED);
        assertThatStatus(handler, result(99, "RVPORT_AUTO_FIX_ALREADY_SATISFIED", null),
                DependencyAutoFixItemStatus.SKIPPED_ALREADY_SATISFIED);
        assertThatStatus(handler, result(11, null, null), DependencyAutoFixItemStatus.SKIPPED_UNAVAILABLE);
        assertThatStatus(handler, result(99, null, "RVPORT_AUTO_FIX_PACKAGE_UNAVAILABLE"),
                DependencyAutoFixItemStatus.SKIPPED_UNAVAILABLE);
        assertThatStatus(handler, result(99, "RVPORT_AUTO_FIX_MAJOR_UNAVAILABLE", null),
                DependencyAutoFixItemStatus.SKIPPED_UNAVAILABLE);
        assertThatStatus(handler, result(14, null, null), DependencyAutoFixItemStatus.FAILED);

        assertThat((DependencyAutoFixRunStatus) ReflectionTestUtils.invokeMethod(
                handler, "finalStatus", Map.of("failed", 1))).isEqualTo(DependencyAutoFixRunStatus.FAILED);
        assertThat((DependencyAutoFixRunStatus) ReflectionTestUtils.invokeMethod(
                handler, "finalStatus", Map.of("succeeded", 1, "failed", 1)))
                .isEqualTo(DependencyAutoFixRunStatus.PARTIALLY_SUCCEEDED);
        assertThat((DependencyAutoFixRunStatus) ReflectionTestUtils.invokeMethod(
                handler, "finalStatus", Map.of("alreadySatisfied", 1, "skippedUnavailable", 1)))
                .isEqualTo(DependencyAutoFixRunStatus.PARTIALLY_SUCCEEDED);
        assertThat((DependencyAutoFixRunStatus) ReflectionTestUtils.invokeMethod(
                handler, "finalStatus", Map.of("succeeded", 1)))
                .isEqualTo(DependencyAutoFixRunStatus.SUCCEEDED);
    }

    @Test
    void sanitizesMessagesAndUsesFallbackTextAtBoundaries() {
        DependencyAutoFixHandler handler = handler();
        assertThat((String) ReflectionTestUtils.invokeMethod(handler, "safeMessage", (String) null)).isEmpty();
        assertThat((String) ReflectionTestUtils.invokeMethod(handler, "safeMessage", " ")).isEmpty();
        assertThat((String) ReflectionTestUtils.invokeMethod(handler, "safeMessage",
                "password=secret\ntoken: abc")).isEqualTo("password=**** token: ****");
        assertThat((String) ReflectionTestUtils.invokeMethod(handler, "safeMessage", "x".repeat(600)))
                .hasSize(500);
        assertThat((String) ReflectionTestUtils.invokeMethod(handler, "firstNonBlank", "first", "second"))
                .isEqualTo("first");
        assertThat((String) ReflectionTestUtils.invokeMethod(handler, "firstNonBlank", " ", "second"))
                .isEqualTo("second");
        assertThat((String) ReflectionTestUtils.invokeMethod(handler, "firstNonBlank", null, null)).isEmpty();
        assertThat((long) ReflectionTestUtils.invokeMethod(handler, "number", "not-number")).isZero();
    }

    private void assertThatStatus(
            DependencyAutoFixHandler handler,
            SshCommandResult result,
            DependencyAutoFixItemStatus expected
    ) {
        assertThat((DependencyAutoFixItemStatus) ReflectionTestUtils.invokeMethod(handler, "status", result))
                .isEqualTo(expected);
    }

    private SshCommandResult result(int exitCode, String stdout, String stderr) {
        return new SshCommandResult(exitCode, stdout, stderr, Duration.ZERO);
    }

    private DependencyAutoFixHandler handler() {
        return new DependencyAutoFixHandler(repository, sshRuntimeService, new DependencyPackageInstallPlanner(),
                dependencyAnalysisService, toolRunRepository);
    }

    private Fixtures fixtures(boolean rerunDependencyAnalysis) {
        UUID projectId = UUID.randomUUID();
        UUID userId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        DependencyAutoFixRunView run = new DependencyAutoFixRunView(UUID.randomUUID(), projectId, taskId,
                UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), 3L, null, null,
                DependencyAutoFixRunStatus.PENDING, 1, 0, 0, 0, Map.of(), null, null, null, OffsetDateTime.now());
        when(context.input(DependencyAutoFixTaskInput.class)).thenReturn(new DependencyAutoFixTaskInput(projectId,
                run.id(), run.dependencyAnalysisRunId(), run.sourceRevisionId(), run.targetEnvironmentId(),
                run.environmentConfigVersion(), rerunDependencyAnalysis));
        when(context.task()).thenReturn(task(taskId, projectId, userId));
        when(repository.findRun(run.id())).thenReturn(java.util.Optional.of(run));
        when(toolRunRepository.create(eq(projectId), eq(taskId), any(), any(), any(), eq(TaskStatus.RUNNING), any()))
                .thenReturn(UUID.randomUUID());
        return new Fixtures(run, userId);
    }

    private TaskView task(UUID taskId, UUID projectId, UUID userId) {
        return new TaskView(taskId, projectId, "DEPENDENCY_AUTO_FIX", TaskStatus.RUNNING,
                0, "running", userId, OffsetDateTime.now(), null, OffsetDateTime.now(),
                null, null, null, null, 0);
    }

    private DependencyAutoFixItemView item(
            UUID runId,
            String packageName,
            String version,
            DependencyRiskLevel riskLevel,
            DependencyAutoFixItemStatus status
    ) {
        return new DependencyAutoFixItemView(UUID.randomUUID(), runId, UUID.randomUUID(), UUID.randomUUID(),
                UUID.randomUUID(), riskLevel, DependencyTargetMatchStatus.REPO_AVAILABLE, packageName, version,
                packageName, version, packageName, version, riskLevel == DependencyRiskLevel.MEDIUM,
                status, null, null, Map.of(), null, null, OffsetDateTime.now());
    }

    private DependencyAutoFixItemView withStatus(DependencyAutoFixItemView item, DependencyAutoFixItemStatus status) {
        return new DependencyAutoFixItemView(item.id(), item.dependencyAutoFixRunId(), item.dependencyResultItemId(),
                item.projectId(), item.sourceRevisionId(), item.riskLevel(), item.targetMatchStatus(),
                item.sourceProviderPackage(), item.sourceProviderVersion(), item.targetProviderPackage(),
                item.targetProviderVersion(), item.installPackageName(), item.installVersionConstraint(),
                item.defaultSelected(), status, item.exitCode(), item.errorSummary(), item.evidence(),
                item.startedAt(), item.finishedAt(), item.createdAt());
    }

    private Map<String, Object> summary(List<DependencyAutoFixItemView> items) {
        return Map.of(
                "total", items.size(),
                "succeeded", items.stream().filter(item -> item.status() == DependencyAutoFixItemStatus.SUCCEEDED).count(),
                "alreadySatisfied", items.stream().filter(item -> item.status() == DependencyAutoFixItemStatus.SKIPPED_ALREADY_SATISFIED).count(),
                "skippedUnavailable", items.stream().filter(item -> item.status() == DependencyAutoFixItemStatus.SKIPPED_UNAVAILABLE).count(),
                "failed", items.stream().filter(item -> item.status() == DependencyAutoFixItemStatus.FAILED).count()
        );
    }

    private record Fixtures(DependencyAutoFixRunView run, UUID userId) {
    }
}
