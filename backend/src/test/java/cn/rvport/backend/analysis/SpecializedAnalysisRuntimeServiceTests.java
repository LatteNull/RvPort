package cn.rvport.backend.analysis;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.artifact.StoredArtifactOwnerType;
import cn.rvport.backend.artifact.StoredArtifactResource;
import cn.rvport.backend.artifact.StoredArtifactService;
import cn.rvport.backend.artifact.StoredArtifactView;
import cn.rvport.backend.config.RvPortProperties;
import cn.rvport.backend.buildvalidation.bitcode.BitcodeReasonCode;
import cn.rvport.backend.buildvalidation.bitcode.BitcodeRuntimeException;
import cn.rvport.backend.buildvalidation.bitcode.BitcodeVerificationFailure;
import cn.rvport.backend.buildvalidation.bitcode.BitcodeVerificationStage;
import cn.rvport.backend.project.ProjectRepository;
import cn.rvport.backend.project.ProjectStage;
import cn.rvport.backend.project.ProjectStatus;
import cn.rvport.backend.project.ProjectView;
import cn.rvport.backend.source.SourceRepository;
import cn.rvport.backend.source.SourceRevisionType;
import cn.rvport.backend.source.SourceRevisionView;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.task.TaskView;
import cn.rvport.backend.worker.TaskCancelledException;
import cn.rvport.backend.worker.TaskExecutionContext;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.NullNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.io.ByteArrayOutputStream;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.time.OffsetDateTime;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicReference;
import org.apache.commons.compress.archivers.tar.TarArchiveEntry;
import org.apache.commons.compress.archivers.tar.TarArchiveOutputStream;
import org.apache.commons.compress.compressors.gzip.GzipCompressorOutputStream;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.core.io.ByteArrayResource;

@ExtendWith(MockitoExtension.class)
class SpecializedAnalysisRuntimeServiceTests {
    @Test
    void memoryOrderStatusVerdictAndExitCodeMustAgree() {
        ObjectNode base = mapper.createObjectNode().put("kind", "UnifiedMemoryOrderAnalysisReport")
                .put("schema_version", 1).put("finding_schema_version", "3.0");
        for (Object[] row : new Object[][] {{0, "complete", "no-finding-within-supported-model"},
                {3, "complete", "risk"}, {2, "partial", "inconclusive"}, {2, "cancelled", "inconclusive"}}) {
            ObjectNode report = base.deepCopy().put("exit_code", (int) row[0]).put("status", (String) row[1]).put("verdict", (String) row[2]);
            org.springframework.test.util.ReflectionTestUtils.invokeMethod(service(), "validateResult", SpecializedAnalyzerType.MEMORY_ORDER, report, row[0]);
        }
        for (Object[] row : new Object[][] {{0, "partial", "no-finding-within-supported-model"},
                {0, "complete", "risk"}, {3, "partial", "risk"}, {3, "complete", "inconclusive"},
                {2, "complete", "inconclusive"}, {2, "partial", "risk"}, {4, "partial", "inconclusive"}}) {
            ObjectNode report = base.deepCopy().put("exit_code", (int) row[0]).put("status", (String) row[1]).put("verdict", (String) row[2]);
            assertThatThrownBy(() -> org.springframework.test.util.ReflectionTestUtils.invokeMethod(service(), "validateResult",
                    SpecializedAnalyzerType.MEMORY_ORDER, report, row[0])).hasMessageContaining("schema");
        }
        ObjectNode mismatch = base.deepCopy().put("schema_version", 2).put("exit_code", 2).put("status", "partial").put("verdict", "inconclusive");
        assertThatThrownBy(() -> org.springframework.test.util.ReflectionTestUtils.invokeMethod(service(), "validateResult",
                SpecializedAnalyzerType.MEMORY_ORDER, mismatch, 2)).hasMessageContaining("schema");
    }

    @Test
    void bundleRejectsSpecialEntriesAndEnforcesExtractionBudgets() throws Exception {
        for (byte type : new byte[] {'1', '2', '3', '4', '6', '5'}) {
            Path bundle = tempDir.resolve("entry-" + type + ".tar.gz");
            try (var gzip = new GzipCompressorOutputStream(Files.newOutputStream(bundle));
                 var tar = new TarArchiveOutputStream(gzip)) {
                var entry = new TarArchiveEntry(type == '5' ? "directory/" : "special", type);
                entry.setLinkName("target");
                tar.putArchiveEntry(entry); tar.closeArchiveEntry();
            }
            Path destination = tempDir.resolve("extracted-" + type);
            if (type == '5') {
                org.springframework.test.util.ReflectionTestUtils.invokeMethod(service(), "extractBundle", bundle, destination);
                assertThat(destination.resolve("directory")).isDirectory();
            } else {
                assertThatThrownBy(() -> org.springframework.test.util.ReflectionTestUtils.invokeMethod(service(), "extractBundle", bundle, destination))
                        .hasMessageContaining("不安全条目");
            }
        }
        Path bundle = Files.write(tempDir.resolve("budget.tar.gz"), bundle("a.bc", "b.bc"));
        assertThatThrownBy(() -> org.springframework.test.util.ReflectionTestUtils.invokeMethod(service(1024, 1024, 1),
                "extractBundle", bundle, tempDir.resolve("files-budget"))).hasMessageContaining("文件数超过预算");
        assertThatThrownBy(() -> org.springframework.test.util.ReflectionTestUtils.invokeMethod(service(1024, 1, 10),
                "extractBundle", bundle, tempDir.resolve("bytes-budget"))).hasMessageContaining("解压大小超过预算");
    }

    @Mock SpecializedAnalysisRepository repository;
    @Mock SpecializedAnalysisCompletionService completionService;
    @Mock StoredArtifactService artifactService;
    @Mock SourceRepository sourceRepository;
    @Mock ProjectRepository projectRepository;
    @Mock SpecializedAnalysisProcessRunner processRunner;
    @Mock SharedBitcodeArtifactVerifier bitcodeArtifactVerifier;
    @Mock TaskExecutionContext context;

    @org.junit.jupiter.api.BeforeEach
    void executeGuardedPublications() {
        org.mockito.Mockito.lenient().when(context.publish(any())).thenAnswer(invocation ->
                invocation.<java.util.function.Supplier<?>>getArgument(0).get());
    }
    @TempDir Path tempDir;

    private final ObjectMapper mapper = new ObjectMapper();
    private UUID projectId;
    private UUID taskId;
    private UUID sourceId;
    private Path sourceRoot;

    @BeforeEach
    void setUp() throws Exception {
        projectId = UUID.randomUUID();
        taskId = UUID.randomUUID();
        sourceId = UUID.randomUUID();
        sourceRoot = Files.createDirectories(tempDir.resolve("source"));
        Files.writeString(sourceRoot.resolve("main.cpp"), "double f(double x) { return x + 0.1; }\n");
        lenient().when(context.task()).thenReturn(new TaskView(taskId, projectId, "ANALYSIS", TaskStatus.RUNNING, 0, null,
                UUID.randomUUID(), OffsetDateTime.now(), null, OffsetDateTime.now(), null, 3600,
                null, null, 0));
    }

    @Test
    void verifiedCapabilityUsesProjectCoverageForAllThreeAnalysisModes() throws Exception {
        SpecializedBitcodeCapability input = new SpecializedBitcodeCapability(
                SpecializedAnalysisMode.AST_ONLY, "PENDING", 9, 0, 0, null,
                null, null, "artifact-set");
        CompileEntryClassification classification = new CompileEntryClassification(
                2, 2, 2,
                List.of(
                        new CompileEntryClassification.ProjectUnit("src/a.cpp", ""),
                        new CompileEntryClassification.ProjectUnit("src/b.cpp", "")),
                Map.of());
        Method method = SpecializedAnalysisRuntimeService.class.getDeclaredMethod(
                "verifiedCapability", SpecializedBitcodeCapability.class,
                CompileEntryClassification.class, CompileEntryClassifier.Coverage.class);
        method.setAccessible(true);

        SpecializedBitcodeCapability empty = (SpecializedBitcodeCapability) method.invoke(
                service(), input, classification, new CompileEntryClassifier.Coverage(2, 0, 1, 1));
        SpecializedBitcodeCapability mixed = (SpecializedBitcodeCapability) method.invoke(
                service(), input, classification, new CompileEntryClassifier.Coverage(2, 1, 1, 0));
        SpecializedBitcodeCapability complete = (SpecializedBitcodeCapability) method.invoke(
                service(), input, classification, new CompileEntryClassifier.Coverage(2, 2, 0, 0));

        assertThat(empty.mode()).isEqualTo(SpecializedAnalysisMode.AST_ONLY);
        assertThat(empty.status()).isEqualTo("INVALID");
        assertThat(empty.degradationReason()).isEqualTo("BITCODE_HAS_NO_USABLE_PROJECT_RECORDS");
        assertThat(mixed.mode()).isEqualTo(SpecializedAnalysisMode.AST_BC_MIXED);
        assertThat(mixed.status()).isEqualTo("PARTIAL");
        assertThat(mixed.degradationReason()).isEqualTo("BITCODE_PARTIAL_PROJECT_COVERAGE");
        assertThat(complete.mode()).isEqualTo(SpecializedAnalysisMode.AST_BC_COMPLETE);
        assertThat(complete.status()).isEqualTo("READY");
        assertThat(complete.degradationReason()).isNull();
        assertThat(complete.audit()).containsKey("translationUnits");
    }

    @Test
    void floatingPointRunImportsBilingualFindingAndArtifacts() throws Exception {
        SpecializedAnalysisTaskInput input = input(SpecializedAnalyzerType.FLOATING_POINT);
        arrangeInputs(input, false);
        AtomicReference<Path> cachePath = new AtomicReference<>();
        when(processRunner.run(any(), any(), eq(context), any())).thenAnswer(invocation -> {
            List<String> command = invocation.getArgument(0);
            if (isAdapter(command)) {
                assertThat(command).contains("--max-frontend-output-bytes", "536870912");
                cachePath.set(argumentPath(command, "--cache"));
                assertThat(cachePath.get().normalize().startsWith(
                        sourceRoot.resolve(".rvport-analysis-cache").normalize())).isTrue();
                Files.writeString(argumentPath(command, "--output"), "{}", StandardCharsets.UTF_8);
                return result(0);
            }
            if (command.contains("scan")) {
                String json = """
                        {"schemaVersion":"2.0","scan":{"status":"complete"},"diagnostics":[],
                         "findings":[{"id":"fp-1","semanticDigest":"digest","fact":{"primaryLocation":{"file":"main.cpp","line":1,"column":8}},
                         "conclusion":{"findingCode":"FP_EQUALITY","category":"precision","severity":"high","confidence":0.9,
                         "status":"confirmed","title":"浮点比较","titleEn":"Floating comparison","message":"存在精度风险",
                         "messageEn":"Precision risk","suggestion":"使用容差","suggestionEn":"Use tolerance",
                         "testSuggestion":"增加边界测试","testSuggestionEn":"Add boundary tests"}}]}
                        """;
                Files.createDirectories(argumentPath(command, "--output").getParent());
                Files.writeString(argumentPath(command, "--output"), json, StandardCharsets.UTF_8);
                return result(0);
            }
            return result(0);
        });
        arrangeStoredArtifacts();

        service().run(input, context);

        @SuppressWarnings("unchecked")
        ArgumentCaptor<List<SpecializedFindingImport>> findings = ArgumentCaptor.forClass(List.class);
        verify(completionService).complete(eq(input), eq(SpecializedAnalysisStatus.COMPLETE), eq("complete"), eq(0),
                any(), any(), any(), any(), eq(null), findings.capture());
        assertThat(findings.getValue()).singleElement().satisfies(finding -> {
            assertThat(finding.findingCode()).isEqualTo("FP_EQUALITY");
            assertThat(finding.title()).isEqualTo("浮点比较");
            assertThat(finding.titleEn()).isEqualTo("Floating comparison");
            assertThat(finding.filePath()).isEqualTo("main.cpp");
            assertThat(finding.startLine()).isEqualTo(1);
        });
        verify(context).progress(100, "浮点精度分析完成");
        assertThat(Files.list(tempDir.resolve("runtime")).toList()).isEmpty();
        assertThat(cachePath.get()).doesNotExist();
        assertThat(sourceRoot.resolve(".rvport-analysis-cache")).doesNotExist();
    }

    @ParameterizedTest
    @EnumSource(FloatingPointEvidenceFixture.class)
    void floatingPointImportPreservesEvidenceStepDescriptionsAndLegacyAbsence(
            FloatingPointEvidenceFixture fixture) throws Exception {
        SpecializedAnalysisTaskInput input = input(SpecializedAnalyzerType.FLOATING_POINT);
        arrangeInputs(input, false);
        ObjectNode expected = fixture.detail(mapper);
        ObjectNode resultJson = mapper.createObjectNode();
        resultJson.put("schemaVersion", "2.0");
        resultJson.putObject("scan").put("status", "partial");
        resultJson.putArray("diagnostics");
        resultJson.putArray("findings").add(expected.deepCopy());
        AtomicReference<JsonNode> archivedJson = new AtomicReference<>();
        when(processRunner.run(any(), any(), eq(context), any())).thenAnswer(invocation -> {
            List<String> command = invocation.getArgument(0);
            if (isAdapter(command)) {
                Files.writeString(argumentPath(command, "--output"), "{}", StandardCharsets.UTF_8);
            } else if (command.contains("scan")) {
                Path output = argumentPath(command, "--output");
                Files.createDirectories(output.getParent());
                Files.writeString(output, mapper.writeValueAsString(resultJson), StandardCharsets.UTF_8);
                return result(4);
            }
            return result(0);
        });
        when(artifactService.storeFile(any(), any(), any(), any(), any(), any(), any(), any(), any(), eq(context)))
                .thenAnswer(invocation -> stored(invocation.getArgument(4), invocation.getArgument(5)));

        doAnswer(invocation -> {
            Path path = invocation.getArgument(5);
            archivedJson.set(mapper.readTree(Files.readString(path, StandardCharsets.UTF_8)));
            return stored(invocation.getArgument(4), path);
        }).when(artifactService).storeLargeFile(any(), any(), any(), any(), any(), any(), any(), any(), any(), eq(context));

        service().run(input, context);

        @SuppressWarnings("unchecked")
        ArgumentCaptor<List<SpecializedFindingImport>> findings = ArgumentCaptor.forClass(List.class);
        verify(completionService).complete(eq(input), eq(SpecializedAnalysisStatus.PARTIAL), eq("partial"), eq(4),
                any(), any(), any(), any(), eq(null), findings.capture());
        assertThat(archivedJson.get()).isEqualTo(resultJson);
        verify(repository).markRunning(input.runId(), "0.5.1");
        assertThat(findings.getValue()).singleElement().satisfies(finding -> {
            assertThat(mapper.<JsonNode>valueToTree(finding.detail())).isEqualTo(expected);
            assertThat(finding.externalFindingId()).isEqualTo("fp-1");
            assertThat(finding.semanticDigest()).isEqualTo("digest");
            assertThat(finding.title()).isEqualTo("浮点比较");
            assertThat(finding.titleEn()).isEqualTo("Floating comparison");
        });
    }

    @Test
    void memoryOrderExitThreeIsSuccessfulAndArchivesAuditOutput() throws Exception {
        SpecializedAnalysisTaskInput input = input(SpecializedAnalyzerType.MEMORY_ORDER);
        arrangeInputs(input, false);
        when(projectRepository.findById(projectId)).thenReturn(Optional.of(new ProjectView(projectId, "demo", null,
                "x86_64", "riscv64", ProjectStage.BUILD_PASSED, ProjectStatus.ACTIVE, null,
                UUID.randomUUID(), OffsetDateTime.now(), OffsetDateTime.now())));
        when(processRunner.run(any(), any(), eq(context), any())).thenAnswer(invocation -> {
            List<String> command = invocation.getArgument(0);
            if (isAdapter(command)) {
                Files.writeString(argumentPath(command, "--output"), "{}", StandardCharsets.UTF_8);
                return result(0);
            }
            Path output = argumentPath(command, "--output");
            Files.createDirectories(output);
            Files.writeString(output.resolve("report.json"), """
                    {"kind":"UnifiedMemoryOrderAnalysisReport","schema_version":1,"finding_schema_version":"2.0","exit_code":3,"status":"complete",
                     "verdict":"risk","diagnostics":[],"findings":[{"schemaVersion":"2.0","id":"mo-1","semantic_digest":"mo-digest",
                     "fact":{"kind":"publication","primaryLocation":{"file":"main.cpp","span":{"start":{"line":3,"column":2},"end":{"line":4,"column":5}}}},
                     "conclusion":{"verdict":"risk","findingType":"weak-ordering","severity":"critical","status":"confirmed",
                     "title":"发布顺序风险","title_en":"Publication ordering risk","detail":"缺少同步","detail_en":"Missing synchronization"}}],
                     "source_candidates":[{"schemaVersion":"2.0","id":"candidate-1","fact":{"kind":"candidate","primaryLocation":{"file":"main.cpp","span":{"start":{"line":8,"column":1},"end":{"line":8,"column":9}}}},
                     "conclusion":{"findingType":"candidate","severity":"medium","status":"inconclusive","detail":"需人工确认"}}]}
                    """, StandardCharsets.UTF_8);
            return result(3);
        });
        arrangeStoredArtifacts();

        service().run(input, context);

        @SuppressWarnings("unchecked")
        ArgumentCaptor<List<SpecializedFindingImport>> findings = ArgumentCaptor.forClass(List.class);
        verify(completionService).complete(eq(input), eq(SpecializedAnalysisStatus.COMPLETE_WITH_RISK), eq("risk"),
                eq(3), any(), any(), any(), any(), any(), findings.capture());
        assertThat(findings.getValue()).hasSize(2);
        assertThat(findings.getValue()).extracting(SpecializedFindingImport::findingKind)
                .containsExactly("FINDING", "SOURCE_CANDIDATE");
        assertThat(findings.getValue().get(1).requiresHumanConfirmation()).isTrue();
    }

    @Test
    void memoryOrderExitZeroPublishesNoRiskResult() throws Exception {
        SpecializedAnalysisTaskInput input = input(SpecializedAnalyzerType.MEMORY_ORDER);
        arrangeInputs(input, false);
        when(projectRepository.findById(projectId)).thenReturn(Optional.of(new ProjectView(projectId, "demo", null,
                "x86_64", "riscv64", ProjectStage.BUILD_PASSED, ProjectStatus.ACTIVE, null,
                UUID.randomUUID(), OffsetDateTime.now(), OffsetDateTime.now())));
        when(processRunner.run(any(), any(), eq(context), any())).thenAnswer(invocation -> {
            List<String> command = invocation.getArgument(0);
            if (isAdapter(command)) {
                Files.writeString(argumentPath(command, "--output"), "{}", StandardCharsets.UTF_8);
                return result(0);
            }
            Path output = argumentPath(command, "--output");
            Files.createDirectories(output);
            Files.writeString(output.resolve("report.json"), """
                    {"kind":"UnifiedMemoryOrderAnalysisReport","schema_version":1,"finding_schema_version":"2.0","exit_code":0,
                     "status":"complete","verdict":"no-finding-within-supported-model","findings":[],
                     "source_candidates":[],"diagnostics":[]}
                    """, StandardCharsets.UTF_8);
            return result(0);
        });
        arrangeStoredArtifacts();

        service().run(input, context);

        verify(completionService).complete(eq(input), eq(SpecializedAnalysisStatus.COMPLETE),
                eq("no-finding-within-supported-model"), eq(0), any(), any(), any(), any(), any(), eq(List.of()));
    }

    @Test
    void sparseFloatingFindingUsesSafeDefaults() throws Exception {
        SpecializedAnalysisTaskInput input = input(SpecializedAnalyzerType.FLOATING_POINT);
        arrangeInputs(input, false);
        when(processRunner.run(any(), any(), eq(context), any())).thenAnswer(invocation -> {
            List<String> command = invocation.getArgument(0);
            if (isAdapter(command)) {
                Files.writeString(argumentPath(command, "--output"), "{}", StandardCharsets.UTF_8);
                return result(0);
            }
            if (!command.contains("scan")) {
                return result(0);
            }
            Files.createDirectories(argumentPath(command, "--output").getParent());
            Files.writeString(argumentPath(command, "--output"), """
                    {"schemaVersion":"2.0","scan":{"status":"complete"},"diagnostics":{},
                     "findings":[{"fact":{},"conclusion":{}}]}
                    """, StandardCharsets.UTF_8);
            return result(0);
        });
        arrangeStoredArtifacts();

        service().run(input, context);

        @SuppressWarnings("unchecked")
        ArgumentCaptor<List<SpecializedFindingImport>> findings = ArgumentCaptor.forClass(List.class);
        verify(completionService).complete(eq(input), eq(SpecializedAnalysisStatus.COMPLETE), eq("complete"), eq(0),
                any(), any(), any(), any(), eq(null), findings.capture());
        assertThat(findings.getValue()).singleElement().satisfies(finding -> {
            assertThat(finding.findingCode()).isEqualTo("floating-point-risk");
            assertThat(finding.filePath()).isNull();
            assertThat(finding.startLine()).isNull();
        });
    }

    @Test
    void unexpectedFailureWithoutMessageIsRecordedSafely() throws Exception {
        SpecializedAnalysisTaskInput input = input(SpecializedAnalyzerType.FLOATING_POINT);
        arrangeInputs(input, false);
        when(processRunner.run(any(), any(), eq(context), any())).thenThrow(new IllegalStateException());

        assertThatThrownBy(() -> service().run(input, context))
                .isInstanceOf(SpecializedAnalysisRuntimeException.class)
                .hasMessageContaining("IllegalStateException");
        verify(repository).fail(eq(input.runId()), eq(SpecializedAnalysisStatus.FAILED),
                org.mockito.ArgumentMatchers.argThat(summary -> "IllegalStateException".equals(summary.get("error"))),
                eq(null), eq(null), eq(0));
    }

    @Test
    void shaMismatchDowngradesToAstOnlyAndStillPublishesResult() throws Exception {
        SpecializedAnalysisTaskInput input = input(SpecializedAnalyzerType.FLOATING_POINT);
        arrangeInputs(input, true);
        arrangeSuccessfulFloatingRun();
        arrangeStoredArtifacts();

        service().run(input, context);

        verify(repository).updateEvidenceMode(eq(input.runId()),
                org.mockito.ArgumentMatchers.argThat(capability -> capability.mode() == SpecializedAnalysisMode.AST_ONLY
                        && "INVALID".equals(capability.status())
                        && "MATERIALIZATION_FAILED".equals(capability.degradationReason())));
        verify(completionService).complete(eq(input), eq(SpecializedAnalysisStatus.COMPLETE), eq("complete"), eq(0),
                org.mockito.ArgumentMatchers.argThat(summary -> "AST_ONLY".equals(summary.get("analysisMode"))),
                any(), any(), any(), eq(null), eq(List.of()));
    }

    @Test
    void structuredBitcodeValidationFailurePreservesStageReasonAndSafeAudit() throws Exception {
        SpecializedAnalysisTaskInput input = input(SpecializedAnalyzerType.FLOATING_POINT);
        arrangeInputs(input, false);
        arrangeSuccessfulFloatingRun();
        arrangeStoredArtifacts();
        BitcodeVerificationFailure failure = new BitcodeVerificationFailure(
                BitcodeVerificationStage.MANIFEST_IDENTITY,
                BitcodeReasonCode.MANIFEST_IDENTITY_MISMATCH,
                "2.0", "21.1.8", "a".repeat(64), "b".repeat(64), "c".repeat(64), false,
                "manifest 摘要不一致 /secret/object-key", "Manifest digest mismatch /secret/object-key",
                "重新生成制品", "Regenerate the artifact");
        doThrow(new BitcodeRuntimeException(failure, null)).when(bitcodeArtifactVerifier)
                .verify(any(), any(), anyInt(), anyLong(), anyLong());

        service().run(input, context);

        verify(repository).updateEvidenceMode(eq(input.runId()),
                org.mockito.ArgumentMatchers.argThat(capability ->
                        "MANIFEST_IDENTITY_MISMATCH".equals(capability.degradationReason())
                        && ((Map<?, ?>) capability.audit().get("validationFailure"))
                                .get("stage").equals("MANIFEST_IDENTITY")
                        && !String.valueOf(capability.audit()).contains("/secret/object-key")));
    }

    @Test
    void cancellationIsRecordedAndPropagated() throws Exception {
        SpecializedAnalysisTaskInput input = input(SpecializedAnalyzerType.FLOATING_POINT);
        arrangeInputs(input, false);
        doThrow(new TaskCancelledException("cancelled")).when(context).throwIfCancellationRequested();

        assertThatThrownBy(() -> service().run(input, context)).isInstanceOf(TaskCancelledException.class);
        verify(repository).fail(input.runId(), SpecializedAnalysisStatus.CANCELLED, "cancelled");
    }

    @Test
    void floatingPointPartialResultSupportsMissingOptionalFields() throws Exception {
        SpecializedAnalysisTaskInput input = input(SpecializedAnalyzerType.FLOATING_POINT);
        arrangeInputs(input, false);
        when(processRunner.run(any(), any(), eq(context), any())).thenAnswer(invocation -> {
            List<String> command = invocation.getArgument(0);
            if (isAdapter(command)) {
                Files.writeString(argumentPath(command, "--output"), "{}", StandardCharsets.UTF_8);
                return result(0);
            }
            if (command.contains("scan")) {
                Files.createDirectories(argumentPath(command, "--output").getParent());
                Files.writeString(argumentPath(command, "--output"), """
                        {"schemaVersion":"2.0","scan":{"status":"partial"},"diagnostics":[],
                         "findings":[{"fact":{"primaryLocation":{}},"conclusion":{"impact":"可能有风险",
                         "impactEn":"Potential risk","confidence":"low","title":" ","severity":"low"}}]}
                        """, StandardCharsets.UTF_8);
                return result(4);
            }
            return result(0);
        });
        arrangeStoredArtifacts();

        service().run(input, context);

        @SuppressWarnings("unchecked")
        ArgumentCaptor<List<SpecializedFindingImport>> findings = ArgumentCaptor.forClass(List.class);
        verify(completionService).complete(eq(input), eq(SpecializedAnalysisStatus.PARTIAL), eq("partial"), eq(4),
                any(), any(), any(), any(), eq(null), findings.capture());
        assertThat(findings.getValue()).singleElement().satisfies(value -> {
            assertThat(value.externalFindingId()).isEqualTo("floating_point-1");
            assertThat(value.findingCode()).isEqualTo("floating-point-risk");
            assertThat(value.title()).isEqualTo("floating-point-risk");
            assertThat(value.startLine()).isNull();
        });
    }

    @Test
    void memoryOrderPartialResultSupportsLocationWithoutSpan() throws Exception {
        SpecializedAnalysisTaskInput input = input(SpecializedAnalyzerType.MEMORY_ORDER);
        arrangeInputs(input, false);
        when(projectRepository.findById(projectId)).thenReturn(Optional.of(new ProjectView(projectId, "demo", null,
                "x86_64", "riscv64", ProjectStage.BUILD_PASSED, ProjectStatus.ACTIVE, null,
                UUID.randomUUID(), OffsetDateTime.now(), OffsetDateTime.now())));
        when(processRunner.run(any(), any(), eq(context), any())).thenAnswer(invocation -> {
            List<String> command = invocation.getArgument(0);
            if (isAdapter(command)) {
                Files.writeString(argumentPath(command, "--output"), "{}", StandardCharsets.UTF_8);
                return result(0);
            }
            Path output = argumentPath(command, "--output");
            Files.createDirectories(output);
            Files.writeString(output.resolve("report.json"), """
                    {"kind":"UnifiedMemoryOrderAnalysisReport","schema_version":1,"finding_schema_version":"2.0","exit_code":2,
                     "status":"partial","verdict":"inconclusive","diagnostics":[{"code":"LIMIT"}],
                     "findings":[{"schemaVersion":"2.0","fact":{"kind":"ordering","primaryLocation":{"file":"main.cpp","line":7,"column":3}},
                     "conclusion":{"reason":"证据不完整","reason_en":"Incomplete evidence"}}]}
                    """, StandardCharsets.UTF_8);
            return result(2);
        });
        arrangeStoredArtifacts();

        service().run(input, context);

        verify(completionService).complete(eq(input), eq(SpecializedAnalysisStatus.PARTIAL), eq("inconclusive"), eq(2),
                org.mockito.ArgumentMatchers.argThat(summary -> Integer.valueOf(1).equals(summary.get("diagnosticCount"))),
                any(), any(), any(), any(), any());
    }

    @Test
    void adapterAndRequestValidationFailuresDoNotPublishResults() throws Exception {
        SpecializedAnalysisTaskInput adapterFailure = input(SpecializedAnalyzerType.FLOATING_POINT);
        arrangeInputs(adapterFailure, false);
        when(processRunner.run(any(), any(), eq(context), any())).thenReturn(result(2));
        assertThatThrownBy(() -> service().run(adapterFailure, context))
                .isInstanceOf(SpecializedAnalysisRuntimeException.class).hasMessageContaining("适配失败");

        SpecializedAnalysisTaskInput validationFailure = input(SpecializedAnalyzerType.FLOATING_POINT);
        arrangeInputs(validationFailure, false);
        when(processRunner.run(any(), any(), eq(context), any())).thenAnswer(invocation -> {
            List<String> command = invocation.getArgument(0);
            if (isAdapter(command)) {
                Files.writeString(argumentPath(command, "--output"), "{}", StandardCharsets.UTF_8);
                return result(0);
            }
            return result(2);
        });
        assertThatThrownBy(() -> service().run(validationFailure, context))
                .isInstanceOf(SpecializedAnalysisRuntimeException.class).hasMessageContaining("请求校验失败");
        verify(completionService, org.mockito.Mockito.never()).complete(any(), any(), any(),
                org.mockito.ArgumentMatchers.anyInt(), any(), any(), any(), any(), any(), any());
    }

    @Test
    void missingOrProtocolInvalidResultIsRejected() throws Exception {
        SpecializedAnalysisTaskInput missing = input(SpecializedAnalyzerType.FLOATING_POINT);
        arrangeInputs(missing, false);
        when(processRunner.run(any(), any(), eq(context), any())).thenAnswer(invocation -> {
            List<String> command = invocation.getArgument(0);
            if (isAdapter(command)) Files.writeString(argumentPath(command, "--output"), "{}", StandardCharsets.UTF_8);
            return result(0);
        });
        assertThatThrownBy(() -> service().run(missing, context))
                .isInstanceOf(SpecializedAnalysisRuntimeException.class).hasMessageContaining("未原子发布");

        SpecializedAnalysisTaskInput invalid = input(SpecializedAnalyzerType.FLOATING_POINT);
        arrangeInputs(invalid, false);
        when(processRunner.run(any(), any(), eq(context), any())).thenAnswer(invocation -> {
            List<String> command = invocation.getArgument(0);
            if (isAdapter(command)) {
                Files.writeString(argumentPath(command, "--output"), "{}", StandardCharsets.UTF_8);
            } else if (command.contains("scan")) {
                Files.createDirectories(argumentPath(command, "--output").getParent());
                Files.writeString(argumentPath(command, "--output"), "{\"schemaVersion\":\"future\"}");
            }
            return result(0);
        });
        assertThatThrownBy(() -> service().run(invalid, context))
                .isInstanceOf(SpecializedAnalysisRuntimeException.class).hasMessageContaining("schema");
    }

    @Test
    void manifestIdentityAndUnsafeBundleDowngradeToAstOnly() throws Exception {
        SpecializedAnalysisTaskInput invalidManifest = input(SpecializedAnalyzerType.FLOATING_POINT);
        arrangeInputs(invalidManifest, false, "future", bundle());
        arrangeSuccessfulFloatingRun();
        arrangeStoredArtifacts();
        service().run(invalidManifest, context);

        SpecializedAnalysisTaskInput unsafeBundle = input(SpecializedAnalyzerType.FLOATING_POINT);
        arrangeInputs(unsafeBundle, false, "2.0", bundle("../escape.bc"));
        service().run(unsafeBundle, context);

        SpecializedAnalysisTaskInput duplicateBundle = input(SpecializedAnalyzerType.FLOATING_POINT);
        arrangeInputs(duplicateBundle, false, "2.0", bundle("duplicate.bc", "duplicate.bc"));
        service().run(duplicateBundle, context);

        verify(repository, org.mockito.Mockito.times(3)).updateEvidenceMode(any(),
                org.mockito.ArgumentMatchers.argThat(capability -> capability.mode() == SpecializedAnalysisMode.AST_ONLY
                        && "MATERIALIZATION_FAILED".equals(capability.degradationReason())));
    }

    @Test
    void missingOrInvalidSourceWorkingCopyIsRejected() throws Exception {
        SpecializedAnalysisTaskInput missing = input(SpecializedAnalyzerType.FLOATING_POINT);
        when(sourceRepository.findById(sourceId)).thenReturn(Optional.empty());
        assertThatThrownBy(() -> service().run(missing, context))
                .isInstanceOf(SpecializedAnalysisRuntimeException.class).hasMessageContaining("源码版本不存在");

        SpecializedAnalysisTaskInput invalid = input(SpecializedAnalyzerType.FLOATING_POINT);
        Path regularFile = Files.writeString(tempDir.resolve("not-a-directory"), "x");
        when(sourceRepository.findById(sourceId)).thenReturn(Optional.of(new SourceRevisionView(sourceId, projectId,
                SourceRevisionType.GIT, "main", null, null, null, null, null, regularFile.toString(), null,
                true, UUID.randomUUID(), OffsetDateTime.now())));
        assertThatThrownBy(() -> service().run(invalid, context))
                .isInstanceOf(SpecializedAnalysisRuntimeException.class).hasMessageContaining("工作副本不可用");
    }

    @Test
    void oversizedInputAndExtractionBudgetsAreEnforced() throws Exception {
        SpecializedAnalysisTaskInput oversized = input(SpecializedAnalyzerType.FLOATING_POINT);
        arrangeInputs(oversized, false);
        assertThatThrownBy(() -> service(1, 1024 * 1024, 100).run(oversized, context))
                .isInstanceOf(SpecializedAnalysisRuntimeException.class).hasMessageContaining("输入制品超过");

        SpecializedAnalysisTaskInput tooMany = input(SpecializedAnalyzerType.FLOATING_POINT);
        arrangeInputs(tooMany, false, "2.0", bundle("one.bc", "two.bc"));
        arrangeSuccessfulFloatingRun();
        arrangeStoredArtifacts();
        service(1024 * 1024, 1024 * 1024, 1).run(tooMany, context);
        verify(repository).updateEvidenceMode(eq(tooMany.runId()),
                org.mockito.ArgumentMatchers.argThat(capability -> capability.mode() == SpecializedAnalysisMode.AST_ONLY
                        && "MATERIALIZATION_FAILED".equals(capability.degradationReason())));
    }

    @Test
    void memoryOrderProtocolMismatchIsRejected() throws Exception {
        SpecializedAnalysisTaskInput input = input(SpecializedAnalyzerType.MEMORY_ORDER);
        arrangeInputs(input, false);
        when(projectRepository.findById(projectId)).thenReturn(Optional.of(new ProjectView(projectId, "demo", null,
                "x86_64", "riscv64", ProjectStage.BUILD_PASSED, ProjectStatus.ACTIVE, null,
                UUID.randomUUID(), OffsetDateTime.now(), OffsetDateTime.now())));
        when(processRunner.run(any(), any(), eq(context), any())).thenAnswer(invocation -> {
            List<String> command = invocation.getArgument(0);
            if (isAdapter(command)) {
                Files.writeString(argumentPath(command, "--output"), "{}", StandardCharsets.UTF_8);
                return result(0);
            }
            Path output = argumentPath(command, "--output");
            Files.createDirectories(output);
            Files.writeString(output.resolve("report.json"), """
                    {"kind":"WrongReport","schema_version":2,"exit_code":0,"status":"complete"}
                    """, StandardCharsets.UTF_8);
            return result(0);
        });

        assertThatThrownBy(() -> service().run(input, context))
                .isInstanceOf(SpecializedAnalysisRuntimeException.class).hasMessageContaining("schema");
    }

    @Test
    void resultStatusAndExitCodeMismatchIsRejected() throws Exception {
        SpecializedAnalysisTaskInput floating = input(SpecializedAnalyzerType.FLOATING_POINT);
        arrangeInputs(floating, false);
        when(processRunner.run(any(), any(), eq(context), any())).thenAnswer(invocation -> {
            List<String> command = invocation.getArgument(0);
            if (isAdapter(command)) {
                Files.writeString(argumentPath(command, "--output"), "{}", StandardCharsets.UTF_8);
                return result(0);
            }
            if (command.contains("scan")) {
                Path output = argumentPath(command, "--output");
                Files.createDirectories(output.getParent());
                Files.writeString(output, """
                        {"schemaVersion":"2.0","scan":{"status":"partial"},
                         "diagnostics":[{"code":"scan_failed","messageEn":"Scanner failed."}]}
                        """, StandardCharsets.UTF_8);
            }
            return result(0);
        });
        assertThatThrownBy(() -> service().run(floating, context))
                .isInstanceOf(SpecializedAnalysisRuntimeException.class)
                .hasMessageContaining("退出码")
                .hasMessageContaining("scan_failed")
                .hasMessageContaining("Scanner failed.");

        SpecializedAnalysisTaskInput memory = input(SpecializedAnalyzerType.MEMORY_ORDER);
        arrangeInputs(memory, false);
        when(projectRepository.findById(projectId)).thenReturn(Optional.of(new ProjectView(projectId, "demo", null,
                "x86_64", "riscv64", ProjectStage.BUILD_PASSED, ProjectStatus.ACTIVE, null,
                UUID.randomUUID(), OffsetDateTime.now(), OffsetDateTime.now())));
        when(processRunner.run(any(), any(), eq(context), any())).thenAnswer(invocation -> {
            List<String> command = invocation.getArgument(0);
            if (isAdapter(command)) {
                Files.writeString(argumentPath(command, "--output"), "{}", StandardCharsets.UTF_8);
                return result(0);
            }
            Path output = argumentPath(command, "--output");
            Files.createDirectories(output);
            Files.writeString(output.resolve("report.json"), """
                    {"kind":"UnifiedMemoryOrderAnalysisReport","schema_version":1,"finding_schema_version":"2.0","exit_code":3,
                     "status":"complete","verdict":"no-finding-within-supported-model"}
                    """, StandardCharsets.UTF_8);
            return result(3);
        });
        assertThatThrownBy(() -> service().run(memory, context))
                .isInstanceOf(SpecializedAnalysisRuntimeException.class).hasMessageContaining("状态或退出码");
    }

    @Test
    void failedFloatingResultIsSanitizedStoredAndUsesCausalDiagnostic() throws Exception {
        SpecializedAnalysisTaskInput input = input(SpecializedAnalyzerType.FLOATING_POINT);
        arrangeInputs(input, false);
        when(artifactService.storeLargeFile(any(), any(), any(), any(), any(), any(), any(), any(), any(), eq(context)))
                .thenAnswer(invocation -> stored(invocation.getArgument(4), invocation.getArgument(5)));
        when(processRunner.run(any(), any(), eq(context), any())).thenAnswer(invocation -> {
            List<String> command = invocation.getArgument(0);
            if (isAdapter(command)) {
                Files.writeString(argumentPath(command, "--output"), "{}", StandardCharsets.UTF_8);
                return result(0);
            }
            if (command.contains("scan")) {
                Path output = argumentPath(command, "--output");
                Files.createDirectories(output.getParent());
                Files.writeString(output, """
                        {"schemaVersion":"2.0","scan":{"status":"failed"},"findings":[],
                         "diagnostics":[
                          {"code":"source_fact_bundle_missing","stage":"source_facts","message":"派生错误",
                           "messageEn":"Derived error","retryable":false},
                          {"code":"frontend_output_limit_exceeded","stage":"frontend",
                           "message":"AST 超限 %s","messageEn":"AST exceeded %s","retryable":false}]}
                        """.formatted(sourceRoot.toString().replace('\\', '/'),
                                sourceRoot.toString().replace('\\', '/')), StandardCharsets.UTF_8);
                return result(2);
            }
            return result(0);
        });

        assertThatThrownBy(() -> service().run(input, context))
                .isInstanceOf(SpecializedAnalysisRuntimeException.class)
                .hasMessageContaining("frontend_output_limit_exceeded")
                .hasMessageContaining("AST 超限")
                .hasMessageNotContaining(sourceRoot.toString());

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> summary = ArgumentCaptor.forClass(Map.class);
        ArgumentCaptor<UUID> artifactId = ArgumentCaptor.forClass(UUID.class);
        verify(repository).fail(eq(input.runId()), eq(SpecializedAnalysisStatus.FAILED), summary.capture(),
                eq(2), artifactId.capture(), eq(2));
        assertThat(summary.getValue())
                .containsEntry("primaryDiagnosticCode", "frontend_output_limit_exceeded")
                .containsEntry("primaryDiagnosticStage", "frontend")
                .containsEntry("retryable", false);
        assertThat(artifactId.getValue()).isNotNull();
    }

    @Test
    void retryableResourceDiagnosticUsesRetryableTaskCode() throws Exception {
        SpecializedAnalysisTaskInput input = input(SpecializedAnalyzerType.FLOATING_POINT);
        arrangeInputs(input, false);
        when(artifactService.storeLargeFile(any(), any(), any(), any(), any(), any(), any(), any(), any(), eq(context)))
                .thenAnswer(invocation -> stored(invocation.getArgument(4), invocation.getArgument(5)));
        when(processRunner.run(any(), any(), eq(context), any())).thenAnswer(invocation -> {
            List<String> command = invocation.getArgument(0);
            if (isAdapter(command)) {
                Files.writeString(argumentPath(command, "--output"), "{}", StandardCharsets.UTF_8);
                return result(0);
            }
            if (command.contains("scan")) {
                Path output = argumentPath(command, "--output");
                Files.createDirectories(output.getParent());
                Files.writeString(output, """
                        {"schemaVersion":"2.0","scan":{"status":"failed"},"findings":[],
                         "diagnostics":[
                          {"code":"result_invalid","stage":"result_validation","message":"结果错误",
                           "messageEn":"Result error","retryable":false},
                          {"code":"worker_busy","stage":"ir_worker","message":"资源暂不可用",
                           "messageEn":"Resource temporarily unavailable","retryable":true},
                          {"code":"unknown","stage":"other","message":"其他错误",
                           "messageEn":"Other error","retryable":false}]}
                        """, StandardCharsets.UTF_8);
                return result(2);
            }
            return result(0);
        });

        assertThatThrownBy(() -> service().run(input, context))
                .isInstanceOf(SpecializedAnalysisRuntimeException.class)
                .extracting("errorCode")
                .isEqualTo("ANALYSIS_RETRYABLE_RESOURCE");
    }

    @Test
    void unsafeFailureArtifactFallsBackToMinimalSummary() throws Exception {
        SpecializedAnalysisTaskInput input = input(SpecializedAnalyzerType.FLOATING_POINT);
        arrangeInputs(input, false);
        when(artifactService.storeLargeFile(any(), any(), any(), any(), any(), any(), any(), any(), any(), eq(context)))
                .thenThrow(new IllegalStateException("storage unavailable"));
        when(processRunner.run(any(), any(), eq(context), any())).thenAnswer(invocation -> {
            List<String> command = invocation.getArgument(0);
            if (isAdapter(command)) {
                Files.writeString(argumentPath(command, "--output"), "{}", StandardCharsets.UTF_8);
                return result(0);
            }
            if (command.contains("scan")) {
                Path output = argumentPath(command, "--output");
                Files.createDirectories(output.getParent());
                Files.writeString(output, """
                        {"schemaVersion":"2.0","scan":{"status":"failed"},"findings":[],
                         "diagnostics":[{"code":"invalid_input","stage":"input","message":"输入错误",
                         "messageEn":"Invalid input","retryable":false}]}
                        """, StandardCharsets.UTF_8);
                return result(2);
            }
            return result(0);
        });

        assertThatThrownBy(() -> service().run(input, context))
                .isInstanceOf(SpecializedAnalysisRuntimeException.class);

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> summary = ArgumentCaptor.forClass(Map.class);
        verify(repository).fail(eq(input.runId()), eq(SpecializedAnalysisStatus.FAILED), summary.capture(),
                eq(2), eq(null), eq(1));
        assertThat(summary.getValue())
                .containsEntry("resultArtifactStored", false)
                .containsEntry("artifactError", "失败结果未通过安全持久化校验");
    }

    @Test
    void diagnosticSelectionAndStructuredSanitizationCoverBoundaryShapes() {
        SpecializedAnalysisRuntimeService service = service();
        ArrayNode diagnostics = mapper.createArrayNode()
                .add(mapper.createObjectNode().put("code", "unknown-stage"))
                .add(mapper.createObjectNode().put("code", "result").put("stage", "result"))
                .add(mapper.createObjectNode().put("code", "evidence").put("stage", "evidence"))
                .add(mapper.createObjectNode().put("code", "ir").put("stage", "ir"))
                .add(mapper.createObjectNode().put("code", "input").put("stage", "input"));

        assertThat(service.primaryDiagnostic(mapper.createObjectNode()).isMissingNode()).isTrue();
        assertThat(service.primaryDiagnostic(mapper.createArrayNode()).isMissingNode()).isTrue();
        assertThat(service.primaryDiagnostic(diagnostics).path("code").asText()).isEqualTo("input");
        assertThat(service.diagnosticPriority(null)).isEqualTo(4);
        assertThat(service.diagnosticPriority("UNKNOWN_STAGE")).isEqualTo(4);

        Path root = tempDir.resolve("sensitive-root").toAbsolutePath();
        ObjectNode document = mapper.createObjectNode();
        document.put("path", root.resolve("source.cpp").toString());
        document.set("nullable", NullNode.getInstance());
        document.putArray("values").add(root.resolve("header.hpp").toString()).add(7).add(true);
        var sanitized = service.sanitizeJson(document, List.of(root));

        assertThat(sanitized.path("path").asText()).doesNotContain(root.toString());
        assertThat(sanitized.path("nullable").isNull()).isTrue();
        assertThat(sanitized.path("values").get(0).asText()).contains("<server-path-redacted>");
        assertThat(sanitized.path("values").get(1).asInt()).isEqualTo(7);
        assertThat(service.sanitizeJson(null, List.of(root))).isNull();
    }

    @Test
    void resultReaderRejectsEmptyAndNonObjectJsonDocuments() throws Exception {
        SpecializedAnalysisRuntimeService service = service();
        Path empty = Files.createFile(tempDir.resolve("empty-result.json"));
        Path array = Files.writeString(tempDir.resolve("array-result.json"), "[]", StandardCharsets.UTF_8);

        assertThatThrownBy(() -> service.readSafeResult(empty, sourceRoot, tempDir))
                .isInstanceOf(SpecializedAnalysisRuntimeException.class)
                .hasMessageContaining("不是 JSON 对象");
        assertThatThrownBy(() -> service.readSafeResult(array, sourceRoot, tempDir))
                .isInstanceOf(SpecializedAnalysisRuntimeException.class)
                .hasMessageContaining("不是 JSON 对象");
    }

    @Test
    void resultLocatorRejectsPublishedOutputAboveBudget() throws Exception {
        Path workspace = Files.createDirectories(tempDir.resolve("oversized-result-workspace"));
        Path output = Files.createDirectories(workspace.resolve("output"));
        Files.writeString(output.resolve("result.json"), "12345", StandardCharsets.UTF_8);

        assertThatThrownBy(() -> service(4, 1024, 10)
                .locateResult(SpecializedAnalyzerType.FLOATING_POINT, workspace))
                .isInstanceOf(SpecializedAnalysisRuntimeException.class)
                .hasMessageContaining("分析结果超过大小预算");
    }

    @Test
    void languageContextSummaryPreservesLegacyDefaultAndUnsupportedStandards() throws Exception {
        Path compileDatabase = Files.writeString(tempDir.resolve("language-contexts.json"), """
                [
                  {"file":"legacy.c","arguments":["gcc","-std=gnu89","-c","legacy.c"]},
                  {"file":"default.cpp","arguments":["g++","-c","default.cpp"]},
                  {"file":"future.c","command":"clang -std=vendor-c -c future.c"}
                ]
                """, StandardCharsets.UTF_8);

        assertThat(service().languageContexts(compileDatabase))
                .containsExactly(
                        Map.of("language", "c", "standard", "c89", "dialect", "gnu",
                                "standardSource", "explicit", "standardOption", "-std=gnu89", "compiler", "gcc"),
                        mapWithNullableStandard("c++", "compiler-default", "compiler-default",
                                "compiler-default", null, "g++"),
                        Map.of("language", "c", "standard", "unsupported", "dialect", "iso",
                                "standardSource", "explicit", "standardOption", "-std=vendor-c", "compiler", "clang"));
        assertThat(service().languageContexts(Files.writeString(tempDir.resolve("invalid-contexts.json"), "{}")))
                .isEmpty();
    }

    private SpecializedAnalysisRuntimeService service() {
        return service(1024L * 1024L, 1024L * 1024L, 100);
    }

    private SpecializedAnalysisRuntimeService service(long maxOutputBytes, long maxExtractedBytes, int maxFiles) {
        RvPortProperties.SpecializedAnalysis config = new RvPortProperties.SpecializedAnalysis(true,
                tempDir.resolve("runtime").toString(), 60, maxOutputBytes, 512L * 1024L * 1024L,
                maxExtractedBytes, maxFiles,
                "python", "fp-scanner", "clang", "fp-worker", "python", "mo-worker", "source-worker");
        return new SpecializedAnalysisRuntimeService(repository, completionService, artifactService, sourceRepository,
                projectRepository, mapper, new RvPortProperties(null, null, null, null, config), processRunner,
                bitcodeArtifactVerifier);
    }

    private void arrangeInputs(SpecializedAnalysisTaskInput input, boolean wrongBundleSha) throws Exception {
        arrangeInputs(input, wrongBundleSha, "2.0", bundle());
    }

    private void arrangeInputs(SpecializedAnalysisTaskInput input, boolean wrongBundleSha, String schema,
            byte[] bundle) throws Exception {
        when(sourceRepository.findById(sourceId)).thenReturn(Optional.of(new SourceRevisionView(sourceId, projectId,
                SourceRevisionType.GIT, "main", null, null, null, null, null, sourceRoot.toString(), null,
                true, UUID.randomUUID(), OffsetDateTime.now())));
        byte[] compile = "[]".getBytes(StandardCharsets.UTF_8);
        byte[] manifest = ("{\"kind\":\"SharedLlvmBitcodeArtifactSet\",\"schema_version\":\"" + schema + "\","
                + "\"artifact_set_id\":\"" + input.artifactSetId() + "\",\"compile_context\":{\"normalized_digest\":\""
                + "c".repeat(64) + "\"},\"producer\":{},\"records\":[],\"scopes\":[]}")
                .getBytes(StandardCharsets.UTF_8);
        mockDownload(input.compileDatabaseArtifactId(), "COMPILE", compile, sha(compile));
        mockDownload(input.bitcodeManifestArtifactId(), "MANIFEST", manifest, sha(manifest));
        mockDownload(input.bitcodeBundleArtifactId(), "BUNDLE", bundle, wrongBundleSha ? "0".repeat(64) : sha(bundle));
    }

    private void mockDownload(UUID id, String type, byte[] bytes, String sha) {
        StoredArtifactView artifact = new StoredArtifactView(id, projectId, taskId,
                StoredArtifactOwnerType.BUILD_VALIDATION, UUID.randomUUID(), type, "bucket", type,
                "application/octet-stream", bytes.length, sha, Map.of(), OffsetDateTime.now());
        lenient().when(artifactService.download(id))
                .thenReturn(new StoredArtifactResource(artifact, new ByteArrayResource(bytes)));
    }

    private void arrangeStoredArtifacts() throws Exception {
        when(artifactService.storeFile(any(), any(), any(), any(), any(), any(), any(), any(), any(), eq(context)))
                .thenAnswer(invocation -> stored(invocation.getArgument(4), invocation.getArgument(5)));
        when(artifactService.storeLargeFile(any(), any(), any(), any(), any(), any(), any(), any(), any(), eq(context)))
                .thenAnswer(invocation -> stored(invocation.getArgument(4), invocation.getArgument(5)));
    }

    private void arrangeSuccessfulFloatingRun() throws Exception {
        when(processRunner.run(any(), any(), eq(context), any())).thenAnswer(invocation -> {
            List<String> command = invocation.getArgument(0);
            if (isAdapter(command)) {
                Files.writeString(argumentPath(command, "--output"), "{}", StandardCharsets.UTF_8);
                return result(0);
            }
            if (command.contains("scan")) {
                Path output = argumentPath(command, "--output");
                Files.createDirectories(output.getParent());
                Files.writeString(output, """
                        {"schemaVersion":"2.0","scan":{"status":"complete"},
                         "diagnostics":[],"findings":[]}
                        """, StandardCharsets.UTF_8);
            }
            return result(0);
        });
    }

    private StoredArtifactView stored(String type, Path path) throws Exception {
        return new StoredArtifactView(UUID.randomUUID(), projectId, taskId, StoredArtifactOwnerType.SPECIALIZED_ANALYSIS,
                UUID.randomUUID(), type, "bucket", type, Files.probeContentType(path), Files.size(path), sha(Files.readAllBytes(path)),
                Map.of(), OffsetDateTime.now());
    }

    private SpecializedAnalysisTaskInput input(SpecializedAnalyzerType type) {
        return new SpecializedAnalysisTaskInput(projectId, UUID.randomUUID(), sourceId, UUID.randomUUID(),
                UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), "a".repeat(64),
                type == SpecializedAnalyzerType.FLOATING_POINT ? 7L : null, type);
    }

    private byte[] bundle() throws Exception {
        return bundle("module.bc");
    }

    private byte[] bundle(String name) throws Exception {
        return bundle(new String[] {name});
    }

    private byte[] bundle(String... names) throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (GzipCompressorOutputStream gzip = new GzipCompressorOutputStream(bytes);
             TarArchiveOutputStream tar = new TarArchiveOutputStream(gzip)) {
            byte[] content = "BC fixture".getBytes(StandardCharsets.UTF_8);
            for (String name : names) {
                TarArchiveEntry entry = new TarArchiveEntry(name);
                entry.setSize(content.length);
                tar.putArchiveEntry(entry);
                tar.write(content);
                tar.closeArchiveEntry();
            }
            tar.finish();
        }
        return bytes.toByteArray();
    }

    private Path argumentPath(List<String> command, String name) {
        return Path.of(command.get(command.indexOf(name) + 1));
    }

    private boolean isAdapter(List<String> command) {
        return command.stream().anyMatch(value -> value.endsWith("prepare_specialized_analysis.py"));
    }

    private SpecializedAnalysisProcessRunner.ProcessResult result(int exitCode) {
        return new SpecializedAnalysisProcessRunner.ProcessResult(exitCode, "ok");
    }

    private Map<String, Object> mapWithNullableStandard(String language, String standard, String dialect,
            String source, String option, String compiler) {
        Map<String, Object> result = new java.util.LinkedHashMap<>();
        result.put("language", language);
        result.put("standard", standard);
        result.put("dialect", dialect);
        result.put("standardSource", source);
        result.put("standardOption", option);
        result.put("compiler", compiler);
        return result;
    }

    private String sha(byte[] bytes) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }
}
