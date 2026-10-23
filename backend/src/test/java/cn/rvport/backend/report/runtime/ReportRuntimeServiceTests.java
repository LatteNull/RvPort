package cn.rvport.backend.report.runtime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.artifact.StoredArtifactCreateCommand;
import cn.rvport.backend.artifact.StoredArtifactOwnerType;
import cn.rvport.backend.artifact.StoredArtifactRepository;
import cn.rvport.backend.artifact.StoredArtifactService;
import cn.rvport.backend.artifact.StoredArtifactView;
import cn.rvport.backend.archive.ArchiveCandidateRegistrar;
import cn.rvport.backend.migration.MigrationInputRefView;
import cn.rvport.backend.migration.MigrationInputService;
import cn.rvport.backend.migration.MigrationInputSourceResolver;
import cn.rvport.backend.migration.MigrationInputSourceType;
import cn.rvport.backend.migration.MigrationInputStatus;
import cn.rvport.backend.report.ReportDownloadFormat;
import cn.rvport.backend.report.ReportGenerateInput;
import cn.rvport.backend.report.ReportInputProjection;
import cn.rvport.backend.report.ReportRepository;
import cn.rvport.backend.report.ReportType;
import cn.rvport.backend.report.ReportView;
import cn.rvport.backend.task.RvPortTaskTypes;
import cn.rvport.backend.task.TaskErrorCode;
import cn.rvport.backend.task.TaskExecutionException;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.task.TaskView;
import cn.rvport.backend.worker.TaskExecutionContext;
import cn.rvport.backend.worker.TaskCancelledException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class ReportRuntimeServiceTests {

    @Mock
    private ReportRepository reportRepository;

    @Mock
    private MigrationInputService migrationInputService;

    @Mock
    private MigrationInputSourceResolver sourceResolver;

    @Mock
    private ReportStatusWriter reportStatusWriter;

    @Mock
    private StoredArtifactRepository storedArtifactRepository;

    @Mock
    private StoredArtifactService storedArtifactService;

    @Mock
    private ArchiveCandidateRegistrar archiveCandidateRegistrar;

    @Mock
    private TaskExecutionContext context;

    @org.junit.jupiter.api.BeforeEach
    void allowPublication() {
        lenient().when(context.publish(any())).thenAnswer(call -> ((java.util.function.Supplier<?>) call.getArgument(0)).get());
    }

    @Test
    void generatesJsonHtmlArtifactsWithRiskWorkloadAndLogo() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID reportId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        ReportView report = report(reportId, projectId, sourceRevisionId, taskId, TaskStatus.RUNNING);
        MigrationInputRefView kb = ref(projectId, sourceRevisionId, MigrationInputSourceType.KB_FINDING, "critical", "src/main.c:1", "替换 x86 intrinsic");
        MigrationInputRefView dependency = ref(projectId, sourceRevisionId, MigrationInputSourceType.DEPENDENCY_RESULT, "HIGH/NO_ALTERNATIVE", "package:gcc@14", "确认目标源可替代包");
        when(context.task()).thenReturn(task(taskId, projectId));
        when(reportRepository.findById(reportId)).thenReturn(Optional.of(report));
        when(migrationInputService.currentConfirmedRefsForSystem(projectId, sourceRevisionId)).thenReturn(List.of(kb, dependency));
        when(sourceResolver.detail(kb)).thenReturn(Map.of("filePath", "src/main.c"));
        when(sourceResolver.detail(dependency)).thenReturn(Map.of("component", "gcc"));

        service().generate(new ReportGenerateInput(projectId, sourceRevisionId, reportId), context);

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, ?>> summaryCaptor = ArgumentCaptor.forClass(Map.class);
        verify(reportStatusWriter).markSucceeded(eq(reportId), summaryCaptor.capture(), eq("CRITICAL"));
        Map<String, ?> summary = summaryCaptor.getValue();
        assertThat(summary.get("highRiskIssueCount")).isEqualTo(2L);
        assertThat(summary.get("estimatedWorkload").toString()).contains("person_hour").contains("6.0").contains("12.0");
        assertThat(summary.get("priorityIssues").toString()).contains("src/main.c:1").contains("package:gcc@14");
        assertThat(summary.get("dependencySubstitutionNotes").toString()).contains("NO_ALTERNATIVE").contains("缺少直接替代");

        @SuppressWarnings("unchecked")
        ArgumentCaptor<List<ReportRepository.ReportInputSnapshot>> inputCaptor = ArgumentCaptor.forClass(List.class);
        verify(reportRepository).replaceInputs(eq(reportId), inputCaptor.capture());
        assertThat(inputCaptor.getValue()).hasSize(2);
        assertThat(inputCaptor.getValue().getFirst().snapshot()).containsEntry("note", "confirmed note");
        assertThat(inputCaptor.getValue().getFirst().snapshot().toString()).doesNotContain("bucket").doesNotContain("objectKey");

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> jsonCaptor = ArgumentCaptor.forClass(Map.class);
        verify(storedArtifactService).storeJson(
                eq(projectId),
                eq(taskId),
                eq(StoredArtifactOwnerType.MIGRATION_REPORT),
                eq(reportId),
                eq(ReportDownloadFormat.JSON.artifactType()),
                jsonCaptor.capture(),
                any(), eq(context)
        );
        assertThat(jsonCaptor.getValue().toString()).contains("migration-report/v2").contains("majorRisks").contains("codeModules");

        ArgumentCaptor<StoredArtifactCreateCommand> htmlCaptor = ArgumentCaptor.forClass(StoredArtifactCreateCommand.class);
        verify(storedArtifactService).store(htmlCaptor.capture(), eq(context));
        String html = new String(htmlCaptor.getValue().content(), StandardCharsets.UTF_8);
        assertThat(html).contains("<svg").contains("高风险问题").contains("预计工作量").contains("主要风险").contains("依赖替代性");
    }

    @Test
    void keepsPathTraversalDetailInReportButDoesNotFailArchiveCandidateRegistration() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID reportId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        ReportView report = report(reportId, projectId, sourceRevisionId, taskId, TaskStatus.RUNNING);
        MigrationInputRefView dependency = ref(projectId, sourceRevisionId, MigrationInputSourceType.DEPENDENCY_RESULT,
                "INFO/MANUAL_CONFIRM_REQUIRED", "include:../include", "人工确认 include 路径");
        when(context.task()).thenReturn(task(taskId, projectId));
        when(reportRepository.findById(reportId)).thenReturn(Optional.of(report));
        when(migrationInputService.currentConfirmedRefsForSystem(projectId, sourceRevisionId)).thenReturn(List.of(dependency));
        when(sourceResolver.detail(dependency)).thenReturn(Map.of(
                "dependencyType", "BUILD_PACKAGE",
                "dependencyName", "../include",
                "targetMatchStatus", "MANUAL_CONFIRM_REQUIRED"
        ));

        service().generate(new ReportGenerateInput(projectId, sourceRevisionId, reportId), context);

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> jsonCaptor = ArgumentCaptor.forClass(Map.class);
        verify(storedArtifactService).storeJson(any(), any(), any(), any(), any(), jsonCaptor.capture(), any(), eq(context));
        assertThat(jsonCaptor.getValue().toString()).contains("include:../include");
        verify(archiveCandidateRegistrar).registerMigrationReport(any(), any(), any());
    }

    @Test
    void preservesSucceededReportWhenArchiveCandidateRegistrationFails() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID reportId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        ReportView report = report(reportId, projectId, sourceRevisionId, taskId, TaskStatus.RUNNING);
        MigrationInputRefView kb = ref(projectId, sourceRevisionId, MigrationInputSourceType.KB_FINDING, "HIGH", "src/main.c:1", "修复");
        when(context.task()).thenReturn(task(taskId, projectId));
        when(reportRepository.findById(reportId)).thenReturn(Optional.of(report));
        when(migrationInputService.currentConfirmedRefsForSystem(projectId, sourceRevisionId)).thenReturn(List.of(kb));
        when(sourceResolver.detail(kb)).thenReturn(Map.of("filePath", "src/main.c"));
        org.mockito.Mockito.doThrow(new IllegalArgumentException("Path traversal ../include"))
                .when(archiveCandidateRegistrar).registerMigrationReport(any(), any(), any());

        service().generate(new ReportGenerateInput(projectId, sourceRevisionId, reportId), context);

        verify(reportStatusWriter).markSucceeded(eq(reportId), any(), eq("HIGH"));
        verify(context).log(eq(cn.rvport.backend.task.TaskLogType.STDERR), org.mockito.ArgumentMatchers.contains("<parent-path-redacted>"));
    }

    @Test
    void regeneratedReportUsesOnlyCurrentConfirmedInputsAfterNodeRerunRefresh() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID reportId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        ReportView report = report(reportId, projectId, sourceRevisionId, taskId, TaskStatus.RUNNING);
        MigrationInputRefView latest = ref(projectId, sourceRevisionId, MigrationInputSourceType.DEPENDENCY_RESULT,
                "MEDIUM/TARGET_AVAILABLE", "package:zlib@1.2", "安装目标依赖包");
        when(context.task()).thenReturn(task(taskId, projectId));
        when(reportRepository.findById(reportId)).thenReturn(Optional.of(report));
        when(migrationInputService.currentConfirmedRefsForSystem(projectId, sourceRevisionId)).thenReturn(List.of(latest));
        when(sourceResolver.detail(latest)).thenReturn(Map.of(
                "dependencyType", "BUILD_PACKAGE",
                "dependencyName", "zlib",
                "targetMatchStatus", "TARGET_AVAILABLE"
        ));

        service().generate(new ReportGenerateInput(projectId, sourceRevisionId, reportId), context);

        @SuppressWarnings("unchecked")
        ArgumentCaptor<List<ReportRepository.ReportInputSnapshot>> inputCaptor = ArgumentCaptor.forClass(List.class);
        verify(reportRepository).replaceInputs(eq(reportId), inputCaptor.capture());
        assertThat(inputCaptor.getValue()).hasSize(1);
        assertThat(inputCaptor.getValue().toString()).contains("zlib").doesNotContain("libcjson");

        ArgumentCaptor<StoredArtifactCreateCommand> htmlCaptor = ArgumentCaptor.forClass(StoredArtifactCreateCommand.class);
        verify(storedArtifactService).store(htmlCaptor.capture(), eq(context));
        String html = new String(htmlCaptor.getValue().content(), StandardCharsets.UTF_8);
        assertThat(html).contains("zlib").doesNotContain("libcjson");
    }

    @Test
    void generatesPerfectReportWithoutConfirmedInputs() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID reportId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        when(context.task()).thenReturn(task(taskId, projectId));
        when(reportRepository.findById(reportId)).thenReturn(Optional.of(report(reportId, projectId, sourceRevisionId, taskId, TaskStatus.RUNNING)));
        when(migrationInputService.currentConfirmedRefsForSystem(projectId, sourceRevisionId)).thenReturn(List.of());

        service().generate(new ReportGenerateInput(projectId, sourceRevisionId, reportId), context);

        @SuppressWarnings("unchecked")
        ArgumentCaptor<List<ReportRepository.ReportInputSnapshot>> inputCaptor = ArgumentCaptor.forClass(List.class);
        verify(reportRepository).replaceInputs(eq(reportId), inputCaptor.capture());
        assertThat(inputCaptor.getValue()).isEmpty();

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, ?>> summaryCaptor = ArgumentCaptor.forClass(Map.class);
        verify(reportStatusWriter).markSucceeded(eq(reportId), summaryCaptor.capture(), eq("INFO"));
        assertThat(summaryCaptor.getValue().get("confirmedInputCount")).isEqualTo(0);
        assertThat(summaryCaptor.getValue().get("highRiskIssueCount")).isEqualTo(0L);
        assertThat(summaryCaptor.getValue().get("estimatedWorkload").toString()).contains("min=0.0", "max=0.0");

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> jsonCaptor = ArgumentCaptor.forClass(Map.class);
        verify(storedArtifactService).storeJson(any(), any(), any(), any(), any(), jsonCaptor.capture(), any(), eq(context));
        assertThat(jsonCaptor.getValue().get("inputs")).isEqualTo(List.of());
    }

    @Test
    void writesFailedReportSummaryWhenRenderingFails() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID reportId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        ReportView report = report(reportId, projectId, sourceRevisionId, taskId, TaskStatus.RUNNING);
        MigrationInputRefView kb = ref(projectId, sourceRevisionId, MigrationInputSourceType.KB_FINDING, "HIGH", "src/main.c:1", "修复");
        when(context.task()).thenReturn(task(taskId, projectId));
        when(reportRepository.findById(reportId)).thenReturn(Optional.of(report));
        when(migrationInputService.currentConfirmedRefsForSystem(projectId, sourceRevisionId)).thenReturn(List.of(kb));
        when(sourceResolver.detail(kb)).thenThrow(new IllegalStateException("bad /srv/runtime path"));

        assertThatThrownBy(() -> service().generate(new ReportGenerateInput(projectId, sourceRevisionId, reportId), context))
                .isInstanceOf(TaskExecutionException.class)
                .hasMessageContaining("WRITE_INPUT_SNAPSHOT");

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, ?>> summaryCaptor = ArgumentCaptor.forClass(Map.class);
        verify(reportStatusWriter).updateStatus(eq(reportId), eq(TaskStatus.FAILED), summaryCaptor.capture());
        assertThat(summaryCaptor.getValue().get("failureStage")).isEqualTo("WRITE_INPUT_SNAPSHOT");
        assertThat(summaryCaptor.getValue().get("causeMessage").toString()).contains("<server-path-redacted>");
    }

    @Test
    void rejectsInputFromAnotherProjectBeforeReadingMigrationInputs() {
        UUID projectId = UUID.randomUUID();
        UUID otherProjectId = UUID.randomUUID();
        when(context.task()).thenReturn(task(UUID.randomUUID(), projectId));

        assertThatThrownBy(() -> service().generate(new ReportGenerateInput(otherProjectId, UUID.randomUUID(), UUID.randomUUID()), context))
                .isInstanceOf(TaskExecutionException.class)
                .extracting("errorCode")
                .isEqualTo(TaskErrorCode.PROJECT_MISMATCH);
    }

    private ReportRuntimeService service() {
        lenient().when(storedArtifactService.storeJson(any(), any(), any(), any(), any(), any(), any(), eq(context)))
                .thenReturn(storedArtifact(ReportDownloadFormat.JSON.artifactType(), "application/json"));
        lenient().when(storedArtifactService.store(any(), eq(context)))
                .thenReturn(storedArtifact(ReportDownloadFormat.HTML.artifactType(), "text/html"));
        lenient().when(reportStatusWriter.markSucceeded(any(), any(), any()))
                .thenAnswer(invocation -> report(invocation.getArgument(0), UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), TaskStatus.SUCCEEDED));
        return new ReportRuntimeService(reportRepository, migrationInputService, sourceResolver, reportStatusWriter, storedArtifactRepository, storedArtifactService,
                archiveCandidateRegistrar, new ObjectMapper().findAndRegisterModules());
    }

    @ParameterizedTest
    @MethodSource("invalidInputs")
    void rejectsEveryMissingRequiredInput(ReportGenerateInput input) {
        assertThatThrownBy(() -> service().generate(input, context))
                .isInstanceOf(TaskExecutionException.class)
                .extracting("errorCode")
                .isEqualTo(TaskErrorCode.INPUT_INVALID);
    }

    private static List<ReportGenerateInput> invalidInputs() {
        UUID value = UUID.randomUUID();
        return java.util.Arrays.asList(
                null,
                new ReportGenerateInput(null, value, value),
                new ReportGenerateInput(value, null, value),
                new ReportGenerateInput(value, value, null)
        );
    }

    @Test
    void rendersAllDependencyStatusesRiskBandsAndEvidenceShapes() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        UUID reportId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        ReportView report = new ReportView(reportId, projectId, taskId, revisionId, ReportType.EVALUATION,
                TaskStatus.RUNNING, "迁移 <评估> & 报告", Map.of(), null, UUID.randomUUID(), null, OffsetDateTime.now());
        List<MigrationInputRefView> refs = List.of(
                ref(projectId, revisionId, MigrationInputSourceType.DEPENDENCY_RESULT, "HIGH/TARGET_INSTALLED", "package:a", "a"),
                ref(projectId, revisionId, MigrationInputSourceType.DEPENDENCY_RESULT, "MEDIUM/REPO_AVAILABLE", "lib:/a.so", "b"),
                ref(projectId, revisionId, MigrationInputSourceType.DEPENDENCY_RESULT, "LOW/PROVIDES_MATCH", "package:c", "c"),
                ref(projectId, revisionId, MigrationInputSourceType.DEPENDENCY_RESULT, "INFO/SOURCE_BUILD_REQUIRED", "package:d", "d"),
                ref(projectId, revisionId, MigrationInputSourceType.DEPENDENCY_RESULT, "COMMENT/MANUAL_REVIEW", "package:e", "e"),
                ref(projectId, revisionId, MigrationInputSourceType.DEPENDENCY_RESULT, "UNKNOWN/MISSING", "package:f", "f"),
                ref(projectId, revisionId, MigrationInputSourceType.KB_FINDING, null, null, null)
        );
        when(context.task()).thenReturn(task(taskId, projectId));
        when(reportRepository.findById(reportId)).thenReturn(Optional.of(report));
        when(migrationInputService.currentConfirmedRefsForSystem(projectId, revisionId)).thenReturn(refs);
        for (int index = 0; index < refs.size(); index++) {
            MigrationInputRefView ref = refs.get(index);
            if (index == 0) {
                when(sourceResolver.detail(ref)).thenReturn(Map.of("evidence", Map.of(
                        "source", "trace", "targetMatchEvidence", Map.of("matchedBy", "provides", "name", "pkg", "version", "1.0"))));
            } else if (index == 1) {
                when(sourceResolver.detail(ref)).thenReturn(Map.of("evidence", Map.of(
                        "source", "linker", "targetMatchEvidence", Map.of("matchedBy", "name", "name", "liba"))));
            } else {
                when(sourceResolver.detail(ref)).thenReturn(Map.of());
            }
        }

        service().generate(new ReportGenerateInput(projectId, revisionId, reportId), context);

        ArgumentCaptor<StoredArtifactCreateCommand> htmlCaptor = ArgumentCaptor.forClass(StoredArtifactCreateCommand.class);
        verify(storedArtifactService).store(htmlCaptor.capture(), eq(context));
        String html = new String(htmlCaptor.getValue().content(), StandardCharsets.UTF_8);
        assertThat(html)
                .contains("迁移 &lt;评估&gt; &amp; 报告")
                .contains("目标仓库存在候选包", "provider 匹配", "源码构建成本", "自动匹配不足", "缺少直接替代")
                .contains("target=pkg@1.0", "target=liba");
    }

    @Test
    void marksCancelledAndDeletesExistingArtifacts() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        UUID reportId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        StoredArtifactView artifact = storedArtifact("REPORT_JSON", "application/json");
        when(context.task()).thenReturn(task(taskId, projectId));
        when(reportRepository.findById(reportId)).thenReturn(Optional.of(report(reportId, projectId, revisionId, taskId, TaskStatus.RUNNING)));
        when(migrationInputService.currentConfirmedRefsForSystem(projectId, revisionId)).thenThrow(new TaskCancelledException("cancelled"));
        when(storedArtifactRepository.listByOwner(StoredArtifactOwnerType.MIGRATION_REPORT, reportId)).thenReturn(List.of(artifact));

        assertThatThrownBy(() -> service().generate(new ReportGenerateInput(projectId, revisionId, reportId), context))
                .isInstanceOf(TaskCancelledException.class);

        verify(reportStatusWriter).updateStatus(eq(reportId), eq(TaskStatus.CANCELLED), any());
        verify(storedArtifactService).delete(artifact, context);
    }

    @Test
    void lostAttemptDoesNotFailReportOrDeletePublishedArtifacts() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        UUID reportId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        when(context.task()).thenReturn(task(taskId, projectId));
        when(reportRepository.findById(reportId)).thenReturn(Optional.of(report(reportId, projectId, revisionId, taskId, TaskStatus.RUNNING)));
        when(migrationInputService.currentConfirmedRefsForSystem(projectId, revisionId))
                .thenThrow(new cn.rvport.backend.worker.TaskAttemptLostException());
        assertThatThrownBy(() -> service().generate(new ReportGenerateInput(projectId, revisionId, reportId), context))
                .isInstanceOf(cn.rvport.backend.worker.TaskAttemptLostException.class);
        verify(reportStatusWriter, org.mockito.Mockito.never()).updateStatus(eq(reportId), eq(TaskStatus.FAILED), any());
        org.mockito.Mockito.verifyNoInteractions(storedArtifactRepository, storedArtifactService, archiveCandidateRegistrar);
    }

    @Test
    void preservesTaskExecutionErrorWhenBestEffortCleanupFails() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        UUID reportId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        TaskExecutionException failure = new TaskExecutionException("KNOWN_ERROR", "known failure", new IllegalArgumentException());
        when(context.task()).thenReturn(task(taskId, projectId));
        when(reportRepository.findById(reportId)).thenReturn(Optional.of(report(reportId, projectId, revisionId, taskId, TaskStatus.RUNNING)));
        when(migrationInputService.currentConfirmedRefsForSystem(projectId, revisionId)).thenThrow(failure);
        when(storedArtifactRepository.listByOwner(StoredArtifactOwnerType.MIGRATION_REPORT, reportId))
                .thenThrow(new IllegalStateException("cleanup unavailable"));

        assertThatThrownBy(() -> service().generate(new ReportGenerateInput(projectId, revisionId, reportId), context))
                .isSameAs(failure);

        verify(reportStatusWriter).updateStatus(eq(reportId), eq(TaskStatus.FAILED), any());
    }

    @Test
    void fallsBackToOriginalReportAndHandlesTrailingStatusAndEmptyEvidence() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        UUID reportId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        MigrationInputRefView ref = ref(projectId, revisionId, MigrationInputSourceType.DEPENDENCY_RESULT,
                "LOW/", "package:test", "review");
        when(context.task()).thenReturn(task(taskId, projectId));
        when(reportRepository.findById(reportId)).thenReturn(Optional.of(report(reportId, projectId, revisionId, taskId, TaskStatus.RUNNING)));
        when(migrationInputService.currentConfirmedRefsForSystem(projectId, revisionId)).thenReturn(List.of(ref));
        when(sourceResolver.detail(ref)).thenReturn(Map.of("evidence", Map.of()));
        ReportRuntimeService service = service();
        when(reportStatusWriter.markSucceeded(eq(reportId), any(), any())).thenReturn(null);

        service.generate(new ReportGenerateInput(projectId, revisionId, reportId), context);

        verify(archiveCandidateRegistrar).registerMigrationReport(any(), any(), any());
    }

    @Test
    void usesGenericRecommendationForNonDependencyLocation() {
        MigrationInputRefView input = ref(UUID.randomUUID(), UUID.randomUUID(), MigrationInputSourceType.KB_FINDING,
                "INFO/UNKNOWN_STATUS", "src/main.c:10", "review");
        String note = ReflectionTestUtils.invokeMethod(service(), "dependencyNote", input);
        assertThat(note).isEqualTo("需要结合来源详情确认处理方式。");
    }

    @Test
    void coversOrganizationRenderingAndContentHashFallbacks() {
        ReportRuntimeService runtime = service();
        MigrationInputRefView ref = ref(UUID.randomUUID(), UUID.randomUUID(), MigrationInputSourceType.KB_FINDING,
                "HIGH", "src/main.c:1", "fix");
        ReportRepository.ReportInputSnapshot withoutProjection = new ReportRepository.ReportInputSnapshot(ref, Map.of(), null);
        ReportRepository.ReportInputSnapshot withoutFile = new ReportRepository.ReportInputSnapshot(ref, Map.of(),
                ReportInputProjection.none("DEPENDENCY_RESULT", "INFO"));
        ReportInputProjection projection = new ReportInputProjection("KB_FINDING", "HIGH", "module", "module",
                "DIRECTORY", "LOW", List.of(), "file", "src/main.c", "TYPE", 1, 1, null, null,
                "symbol", null, true);
        ReportRepository.ReportInputSnapshot withFile = new ReportRepository.ReportInputSnapshot(ref, Map.of(), projection);

        assertThat((ReportRepository.ReportInputSnapshot) ReflectionTestUtils.invokeMethod(runtime,
                "withContentHash", withoutProjection, Map.of())).isSameAs(withoutProjection);
        assertThat((ReportRepository.ReportInputSnapshot) ReflectionTestUtils.invokeMethod(runtime,
                "withContentHash", withoutFile, Map.of())).isSameAs(withoutFile);
        ReportRepository.ReportInputSnapshot hashed = ReflectionTestUtils.invokeMethod(runtime,
                "withContentHash", withFile, Map.of("file", "sha"));
        assertThat(hashed.projection().sourceContentHash()).isEqualTo("sha");
        ReportRepository.ReportInputSnapshot missingHash = ReflectionTestUtils.invokeMethod(runtime,
                "withContentHash", withFile, Map.of());
        assertThat(missingHash.projection().sourceContentHash()).isNull();

        StringBuilder empty = new StringBuilder();
        ReflectionTestUtils.invokeMethod(runtime, "appendOrganization", empty,
                Map.of("codeModules", "invalid", "dependencyPackages", "invalid"));
        assertThat(empty.toString()).contains("暂无源码迁移问题", "暂无依赖迁移项");

        Map<String, Object> module = Map.of(
                "moduleName", "core", "fileCount", 1, "findingCount", 1, "highestRisk", "HIGH",
                "files", List.of(Map.of("relativePath", "src/main.c", "findingCount", 1,
                        "findingTypes", List.of(Map.of("findingType", "TYPE", "findingCount", 1,
                                "firstLine", 1, "lastLine", 1, "highestRisk", "HIGH", "findings", "invalid")))));
        Map<String, Object> dependency = Map.of("packageName", "gcc", "sourceVersion", "12", "targetVersion", "13",
                "highestRisk", "LOW", "targetMatchStatuses", List.of("TARGET_NEWER"), "dependencyTypes", List.of("BUILD"));
        StringBuilder populated = new StringBuilder();
        ReflectionTestUtils.invokeMethod(runtime, "appendOrganization", populated,
                Map.of("codeModules", List.of(module), "dependencyPackages", List.of(dependency)));
        assertThat(populated.toString()).contains("core", "gcc");

        assertThat((String) ReflectionTestUtils.invokeMethod(runtime, "evidenceSummary", "invalid")).isEmpty();
        assertThat((String) ReflectionTestUtils.invokeMethod(runtime, "workloadText", "invalid")).isEmpty();
        StringBuilder issues = new StringBuilder();
        ReflectionTestUtils.invokeMethod(runtime, "appendIssueList", issues, List.of("invalid"));
        assertThat(issues.toString()).contains("<ul>").doesNotContain("invalid");
        assertThat((String) ReflectionTestUtils.invokeMethod(runtime, "sanitize", "line one\nline two"))
                .isEqualTo("line one\nline two");
        assertThat((String) ReflectionTestUtils.invokeMethod(runtime, "sanitize", "x".repeat(600))).hasSize(500);
    }

    @Test
    void includesDependencyEvidenceFromLocationOrTargetStatusWithoutRetiredSourceTypes() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        UUID reportId = UUID.randomUUID();
        UUID taskId = UUID.randomUUID();
        var packageFinding = ref(projectId, revisionId, MigrationInputSourceType.KB_FINDING,
                "LOW", "package:openssl", "核对目标包");
        var targetFinding = ref(projectId, revisionId, MigrationInputSourceType.KB_FINDING,
                "HIGH/NO_ALTERNATIVE", "src/compat.c", "确认替代方案");
        when(context.task()).thenReturn(task(taskId, projectId));
        when(reportRepository.findById(reportId)).thenReturn(Optional.of(
                report(reportId, projectId, revisionId, taskId, TaskStatus.RUNNING)));
        when(migrationInputService.currentConfirmedRefsForSystem(projectId, revisionId))
                .thenReturn(List.of(packageFinding, targetFinding));
        when(sourceResolver.detail(packageFinding)).thenReturn(Map.of());
        when(sourceResolver.detail(targetFinding)).thenReturn(Map.of());

        service().generate(new ReportGenerateInput(projectId, revisionId, reportId), context);

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, ?>> summary = ArgumentCaptor.forClass(Map.class);
        verify(reportStatusWriter).markSucceeded(eq(reportId), summary.capture(), eq("HIGH"));
        @SuppressWarnings("unchecked")
        var notes = (List<Map<String, Object>>) summary.getValue().get("dependencySubstitutionNotes");
        assertThat(notes).hasSize(2);
        assertThat(notes).extracting(item -> item.get("targetMatchStatus"))
                .containsExactly("NO_ALTERNATIVE", "UNKNOWN");
        assertThat(notes.toString()).contains("package:openssl", "src/compat.c");
    }

    private StoredArtifactView storedArtifact(String artifactType, String contentType) {
        return new StoredArtifactView(
                UUID.randomUUID(),
                UUID.randomUUID(),
                UUID.randomUUID(),
                StoredArtifactOwnerType.MIGRATION_REPORT,
                UUID.randomUUID(),
                artifactType,
                "rvport-artifacts",
                "projects/test/object",
                contentType,
                10,
                "abc123",
                Map.of(),
                OffsetDateTime.now()
        );
    }

    private ReportView report(UUID reportId, UUID projectId, UUID sourceRevisionId, UUID taskId, TaskStatus status) {
        return new ReportView(reportId, projectId, taskId, sourceRevisionId, ReportType.EVALUATION, status,
                "迁移评估报告", Map.of(), null, UUID.randomUUID(), null, OffsetDateTime.now());
    }

    private TaskView task(UUID taskId, UUID projectId) {
        return new TaskView(taskId, projectId, RvPortTaskTypes.REPORT_GENERATE, TaskStatus.RUNNING, 0, "running",
                UUID.randomUUID(), OffsetDateTime.now(), OffsetDateTime.now(), OffsetDateTime.now(), null, 300, null, null, 0);
    }

    private MigrationInputRefView ref(UUID projectId, UUID sourceRevisionId, MigrationInputSourceType sourceType,
                                      String detectedLevel, String locationLabel, String recommendation) {
        return new MigrationInputRefView(
                UUID.randomUUID(),
                UUID.randomUUID(),
                projectId,
                sourceRevisionId,
                sourceType == MigrationInputSourceType.KB_FINDING ? "AVX intrinsic" : "gcc package",
                sourceType,
                UUID.randomUUID(),
                detectedLevel,
                locationLabel,
                recommendation,
                "rule",
                locationLabel,
                "symbol",
                "anchor",
                "fingerprint",
                MigrationInputStatus.CONFIRMED,
                "confirmed note",
                OffsetDateTime.now(),
                OffsetDateTime.now()
        );
    }
}
