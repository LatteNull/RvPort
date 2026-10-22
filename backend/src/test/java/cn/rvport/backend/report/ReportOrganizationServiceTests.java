package cn.rvport.backend.report;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.doReturn;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.artifact.StoredArtifactOwnerType;
import cn.rvport.backend.artifact.StoredArtifactResource;
import cn.rvport.backend.artifact.StoredArtifactService;
import cn.rvport.backend.artifact.StoredArtifactView;
import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.project.ProjectAccessService;
import cn.rvport.backend.task.TaskStatus;
import java.nio.charset.StandardCharsets;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ByteArrayResource;

class ReportOrganizationServiceTests {

    private final ReportRepository reportRepository = mock(ReportRepository.class);
    private final ReportOrganizationRepository organizationRepository = mock(ReportOrganizationRepository.class);
    private final ProjectAccessService projectAccessService = mock(ProjectAccessService.class);
    private final StoredArtifactService storedArtifactService = mock(StoredArtifactService.class);
    private final ReportOrganizationService service = new ReportOrganizationService(
            reportRepository, organizationRepository, projectAccessService, storedArtifactService);
    private final UUID projectId = UUID.randomUUID();
    private final UUID reportId = UUID.randomUUID();
    private final UUID actorId = UUID.randomUUID();
    private final UUID revisionId = UUID.randomUUID();

    @BeforeEach
    void setUp() {
        when(reportRepository.findById(reportId)).thenReturn(Optional.of(report()));
    }

    @Test
    void returnsDirectChildStatisticsFiltersAndStableFindingOrder() {
        List<ReportOrganizedInput> inputs = List.of(
                input("m1", "模块一", "f1", "src/a.c", "HEADER", 20, "HIGH"),
                input("m1", "模块一", "f1", "src/a.c", "INTRINSIC", 5, "MEDIUM"),
                input("m1", "模块一", "f2", "src/b.c", "HEADER", null, "INFO"),
                input("m2", "模块二", "f3", "lib/c.c", "TYPE", 1, "LOW")
        );
        when(organizationRepository.listCodeInputs(reportId)).thenReturn(inputs);

        var modules = service.modules(reportId, request(null, null), actorId, false);
        var files = service.files(reportId, "m1", request(null, null), actorId, false);
        var types = service.findingTypes(reportId, "m1", "f1", request(null, null), actorId, false);
        var findings = service.findings(reportId, "m1", "f1", null, request(null, null), actorId, false);

        assertThat(modules.total()).isEqualTo(2);
        assertThat(modules.items().getFirst()).satisfies(module -> {
            assertThat(module.fileCount()).isEqualTo(2);
            assertThat(module.findingCount()).isEqualTo(3);
            assertThat(module.findingTypeCount()).isEqualTo(2);
            assertThat(module.highestRisk()).isEqualTo("HIGH");
        });
        assertThat(files.items()).extracting(ReportCodeFileResponse::relativePath).containsExactly("src/a.c", "src/b.c");
        assertThat(types.items()).extracting(ReportFindingTypeResponse::findingType).containsExactly("HEADER", "INTRINSIC");
        assertThat(findings.items()).extracting(ReportCodeFindingResponse::lineStart).containsExactly(5, 20);
        verify(projectAccessService, org.mockito.Mockito.atLeastOnce()).requireProjectAccess(projectId, actorId, false);
    }

    @Test
    void supportsPaginationKeywordRiskAndRejectsInvalidSort() {
        when(organizationRepository.listCodeInputs(reportId)).thenReturn(List.of(
                input("m1", "alpha", "f1", "src/a.c", "HEADER", 2, "HIGH"),
                input("m2", "beta", "f2", "src/b.c", "TYPE", 3, "LOW")
        ));

        var filtered = service.modules(reportId, new ReportOrganizationListRequest(1, 1, "HIGH", "alpha", "findingCount", "desc"), actorId, false);
        assertThat(filtered.total()).isEqualTo(1);
        assertThat(filtered.items()).extracting(ReportCodeModuleResponse::moduleName).containsExactly("alpha");

        assertThatThrownBy(() -> service.modules(reportId, request("serverPath", "asc"), actorId, false))
                .isInstanceOf(ApiException.class)
                .extracting("code").isEqualTo("REPORT_ORGANIZATION_QUERY_INVALID");
    }

    @Test
    void returnsCombinedContextWithStructuredOmissionAndHighlights() {
        ReportOrganizedInput early = input("m1", "module", "f1", "src/a.c", "TYPE", 10, "HIGH");
        ReportOrganizedInput late = input("m1", "module", "f1", "src/a.c", "TYPE", 900, "MEDIUM");
        when(organizationRepository.listCodeInputs(reportId)).thenReturn(List.of(early, late));
        UUID artifactId = UUID.randomUUID();
        when(organizationRepository.findFileContext(reportId, "f1")).thenReturn(Optional.of(
                new ReportFileContextView(UUID.randomUUID(), reportId, revisionId, "f1", "src/a.c", "sha", 1000,
                        artifactId, true, null, OffsetDateTime.now())));
        StringBuilder source = new StringBuilder();
        for (int line = 1; line <= 1000; line++) {
            source.append("line ").append(line).append('\n');
        }
        StoredArtifactView artifact = new StoredArtifactView(artifactId, projectId, UUID.randomUUID(),
                StoredArtifactOwnerType.MIGRATION_REPORT, reportId, "SOURCE_CONTEXT_f1", "bucket", "key", "text/plain",
                source.length(), "sha", Map.of(), OffsetDateTime.now());
        when(storedArtifactService.download(artifactId)).thenReturn(new StoredArtifactResource(artifact,
                new ByteArrayResource(source.toString().getBytes(StandardCharsets.UTF_8))));

        ReportFileContextResponse response = service.context(reportId, "f1", new ReportFileContextRequest(null, 500), actorId, false);

        assertThat(response.contextAvailable()).isTrue();
        assertThat(response.blocks()).extracting(ReportFileContextResponse.Block::kind).containsExactly("CODE", "OMITTED", "CODE");
        assertThat(response.blocks().get(1)).satisfies(block -> {
            assertThat(block.reason()).isEqualTo("DISTANT_FINDING_GAP");
            assertThat(block.loadable()).isTrue();
            assertThat(block.lines()).isEmpty();
        });
        assertThat(response.blocks().getFirst().lines()).anyMatch(line -> line.lineNumber() == 10 && !line.highlights().isEmpty());

        ReportFileContextResponse expanded = service.context(reportId, "f1", new ReportFileContextRequest(400, 10), actorId, false);
        assertThat(expanded.blocks()).singleElement().satisfies(block -> {
            assertThat(block.kind()).isEqualTo("CODE");
            assertThat(block.startLine()).isEqualTo(400);
            assertThat(block.endLine()).isEqualTo(409);
        });
    }

    @Test
    void returnsAuditableUnavailableStateWhenSnapshotCannotBeRead() {
        when(organizationRepository.listCodeInputs(reportId)).thenReturn(List.of());
        when(organizationRepository.findFileContext(reportId, "f1")).thenReturn(Optional.of(
                new ReportFileContextView(UUID.randomUUID(), reportId, revisionId, "f1", "src/a.c", null, null,
                        null, false, "BINARY_FILE", OffsetDateTime.now())));

        ReportFileContextResponse response = service.context(reportId, "f1", null, actorId, false);

        assertThat(response.contextAvailable()).isFalse();
        assertThat(response.unavailableReason()).isEqualTo("BINARY_FILE");
        assertThat(response.blocks()).isEmpty();
    }

    @Test
    void rejectsMissingReportAndBlankKeysWithoutLeakingData() {
        UUID missing = UUID.randomUUID();
        when(reportRepository.findById(missing)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.modules(missing, request(null, null), actorId, false))
                .isInstanceOf(ApiException.class).extracting("code").isEqualTo("REPORT_NOT_FOUND");
        assertThatThrownBy(() -> service.files(reportId, " ", request(null, null), actorId, false))
                .isInstanceOf(ApiException.class).extracting("code").isEqualTo("REPORT_MODULE_KEY_REQUIRED");
        assertThatThrownBy(() -> service.context(reportId, "missing", null, actorId, false))
                .isInstanceOf(ApiException.class).extracting("code").isEqualTo("REPORT_FILE_CONTEXT_NOT_FOUND");
    }

    @Test
    void coversAllSupportedSortsDirectionsAndEmptyPages() {
        List<ReportOrganizedInput> inputs = List.of(
                input("m1", "Zulu", "f1", "z.c", "TYPE", 20, "LOW"),
                input("m1", "Zulu", "f1", "z.c", "TYPE", 10, "CRITICAL"),
                input("m1", "Zulu", "f2", "a.c", "HEADER", null, "INFO"),
                input("m2", "Alpha", "f3", "b.c", "OTHER", 5, "MEDIUM")
        );
        when(organizationRepository.listCodeInputs(reportId)).thenReturn(inputs);

        for (String sort : List.of("moduleName", "fileCount", "findingCount", "highestRisk")) {
            assertThat(service.modules(reportId, request(sort, "desc"), actorId, false).items()).hasSize(2);
        }
        for (String sort : List.of("relativePath", "findingCount", "highestRisk")) {
            assertThat(service.files(reportId, "m1", request(sort, "asc"), actorId, false).items()).hasSize(2);
        }
        for (String sort : List.of("findingType", "findingCount", "highestRisk", "firstLine")) {
            assertThat(service.findingTypes(reportId, "m1", "f1", request(sort, "desc"), actorId, false).items()).isNotEmpty();
        }
        for (String sort : List.of("lineStart", "riskLevel", "issueTitle")) {
            assertThat(service.findings(reportId, "m1", "f1", " ", request(sort, "desc"), actorId, false).items()).hasSize(2);
        }

        ReportOrganizationListRequest beyondEnd = new ReportOrganizationListRequest(9, 1, null, null, null, null);
        assertThat(service.modules(reportId, beyondEnd, actorId, false).items()).isEmpty();
        assertThatThrownBy(() -> service.files(reportId, "m1", request("bad", "asc"), actorId, false)).isInstanceOf(ApiException.class);
        assertThatThrownBy(() -> service.findingTypes(reportId, "m1", "f1", request("bad", "asc"), actorId, false)).isInstanceOf(ApiException.class);
        assertThatThrownBy(() -> service.findings(reportId, "m1", "f1", null, request("bad", "asc"), actorId, false)).isInstanceOf(ApiException.class);
        assertThatThrownBy(() -> service.modules(reportId, request("moduleName", "sideways"), actorId, false)).isInstanceOf(ApiException.class);
    }

    @Test
    void filtersAcrossEverySearchableFieldAndNormalizesRisk() {
        List<ReportOrganizedInput> inputs = List.of(
                detailedInput("module-hit", "m1", "path/a.c", "TYPE", "title", "symbol", "HIGH", 1, UUID.randomUUID(), Map.of()),
                detailedInput("module", "m2", "path-hit/a.c", "TYPE", "title", "symbol", "HIGH", 2, null, "not-a-map"),
                detailedInput("module", "m3", "path/a.c", "type-hit", "title", "symbol", "HIGH", 3, null, Map.of()),
                detailedInput("module", "m4", "path/a.c", "TYPE", "title-hit", "symbol", "HIGH", 4, null, Map.of()),
                detailedInput("module", "m5", "path/a.c", "TYPE", "title", "symbol-hit", "HIGH", 5, null, Map.of())
        );
        when(organizationRepository.listCodeInputs(reportId)).thenReturn(inputs);

        for (String keyword : List.of("module-hit", "path-hit", "type-hit", "title-hit", "symbol-hit")) {
            ReportOrganizationListRequest query = new ReportOrganizationListRequest(null, null, " high ", keyword, null, " ");
            assertThat(service.modules(reportId, query, actorId, false).total()).isEqualTo(1);
        }
        assertThat(service.modules(reportId, new ReportOrganizationListRequest(null, null, " ", "missing", null, null), actorId, false).total()).isZero();

        var findings = service.findings(reportId, "m2", "unused", null, request(null, null), actorId, false);
        assertThat(findings.items()).isEmpty();
        var mapped = service.findings(reportId, "m1", "m1", null, request(null, null), actorId, false);
        assertThat(mapped.items()).singleElement().satisfies(item -> {
            assertThat(item.sourceRefId()).isNotNull();
            assertThat(item.sourceDetail()).isEmpty();
        });
    }

    @Test
    void handlesCompactEmptyAndUnreadableContextVariants() {
        ReportOrganizedInput noEnd = detailedInput("module", "m1", "src/a.c", "TYPE", "issue", null,
                "UNKNOWN", 2, "invalid-uuid", Map.of());
        when(organizationRepository.listCodeInputs(reportId)).thenReturn(List.of(noEnd));
        UUID artifactId = UUID.randomUUID();
        ReportFileContextView available = new ReportFileContextView(UUID.randomUUID(), reportId, revisionId, "m1", "src/a.c",
                "sha", 4, artifactId, true, null, OffsetDateTime.now());
        when(organizationRepository.findFileContext(reportId, "m1")).thenReturn(Optional.of(available));
        StoredArtifactView artifact = new StoredArtifactView(artifactId, projectId, UUID.randomUUID(),
                StoredArtifactOwnerType.MIGRATION_REPORT, reportId, "SOURCE_CONTEXT_m1", "bucket", "key", "text/plain",
                8, "sha", Map.of(), OffsetDateTime.now());
        when(storedArtifactService.download(artifactId)).thenReturn(new StoredArtifactResource(artifact,
                new ByteArrayResource("a\nb\nc\n".getBytes(StandardCharsets.UTF_8))));

        ReportFileContextResponse compact = service.context(reportId, "m1", new ReportFileContextRequest(null, 0), actorId, false);
        assertThat(compact.blocks()).singleElement().satisfies(block -> {
            assertThat(block.startLine()).isEqualTo(1);
            assertThat(block.endLine()).isEqualTo(4);
        });
        assertThat(compact.findings()).singleElement().satisfies(finding -> assertThat(finding.sourceRefId()).isNull());

        when(storedArtifactService.download(artifactId)).thenThrow(new IllegalStateException("storage unavailable"));
        ReportFileContextResponse unavailable = service.context(reportId, "m1", new ReportFileContextRequest(99, 10), actorId, false);
        assertThat(unavailable.contextAvailable()).isFalse();
        assertThat(unavailable.unavailableReason()).isEqualTo("CONTEXT_ARTIFACT_UNAVAILABLE");

        when(organizationRepository.listCodeInputs(reportId)).thenReturn(List.of());
        doReturn(new StoredArtifactResource(artifact,
                new ByteArrayResource("a\nb\n".getBytes(StandardCharsets.UTF_8))))
                .when(storedArtifactService).download(artifactId);
        assertThat(service.context(reportId, "m1", null, actorId, false).blocks()).isEmpty();
        assertThat(service.organizationAvailable(reportId)).isFalse();
        verify(organizationRepository).organizationAvailable(reportId);
    }

    @Test
    void rejectsBlankNestedKeys() {
        assertThatThrownBy(() -> service.findingTypes(reportId, "m1", " ", request(null, null), actorId, false))
                .isInstanceOf(ApiException.class).extracting("code").isEqualTo("REPORT_FILE_KEY_REQUIRED");
        assertThatThrownBy(() -> service.findings(reportId, null, "f1", null, request(null, null), actorId, false))
                .isInstanceOf(ApiException.class).extracting("code").isEqualTo("REPORT_MODULE_KEY_REQUIRED");
        assertThatThrownBy(() -> service.findings(reportId, "m1", "", null, request(null, null), actorId, false))
                .isInstanceOf(ApiException.class).extracting("code").isEqualTo("REPORT_FILE_KEY_REQUIRED");
    }

    @Test
    void normalizesSparseOrganizationValuesAndSupportsExplicitRanges() {
        UUID sourceRefId = UUID.randomUUID();
        ReportOrganizedInput sparse = detailedInput("", "unlocated", null, null, null, null,
                null, 1, sourceRefId.toString(), "not-a-map");
        ReportOrganizedInput blankSymbol = new ReportOrganizedInput(UUID.randomUUID(), UUID.randomUUID(), "KB_FINDING", "ALIEN",
                "unlocated", "", "", "", null, "unlocated", null, null, 2, 1,
                null, null, "", null, true, Map.of("issueTitle", "second", "sourceDetail", "invalid"));
        when(organizationRepository.listCodeInputs(reportId)).thenReturn(List.of(sparse, blankSymbol));

        var modules = service.modules(reportId, request(" ", "asc"), actorId, false);
        assertThat(modules.items()).singleElement().satisfies(module -> {
            assertThat(module.moduleName()).isEmpty();
            assertThat(module.highestRisk()).isEqualTo("INFO");
        });
        assertThat(service.files(reportId, "unlocated", request(null, null), actorId, false).items())
                .singleElement().satisfies(file -> assertThat(file.contextAvailable()).isFalse());
        assertThat(service.findingTypes(reportId, "unlocated", "unlocated", request(null, null), actorId, false).items())
                .singleElement().satisfies(type -> {
                    assertThat(type.findingType()).isEqualTo("UNCLASSIFIED");
                    assertThat(type.symbolCount()).isZero();
                });
        assertThat(service.findings(reportId, "unlocated", "unlocated", "", request("issueTitle", "asc"), actorId, false).items())
                .anySatisfy(finding -> {
                    assertThat(finding.sourceRefId()).isEqualTo(sourceRefId);
                    assertThat(finding.sourceDetail()).isEmpty();
                });
        assertThat(service.findings(reportId, "unlocated", "unlocated", "TYPE", request(null, null), actorId, false).items()).isEmpty();
        assertThat(service.modules(reportId,
                new ReportOrganizationListRequest(null, null, null, "anything", null, null), actorId, false).items()).isEmpty();

        UUID artifactId = UUID.randomUUID();
        when(organizationRepository.findFileContext(reportId, "unlocated")).thenReturn(Optional.of(
                new ReportFileContextView(UUID.randomUUID(), reportId, revisionId, "unlocated", "file.c", "sha", 3,
                        artifactId, true, null, OffsetDateTime.now())));
        StoredArtifactView artifact = new StoredArtifactView(artifactId, projectId, UUID.randomUUID(),
                StoredArtifactOwnerType.MIGRATION_REPORT, reportId, "SOURCE_CONTEXT", "bucket", "key", "text/plain",
                6, "sha", Map.of(), OffsetDateTime.now());
        when(storedArtifactService.download(artifactId)).thenReturn(new StoredArtifactResource(artifact,
                new ByteArrayResource("a\nb\nc".getBytes(StandardCharsets.UTF_8))));
        ReportFileContextResponse range = service.context(reportId, "unlocated", new ReportFileContextRequest(2, 20), actorId, false);
        assertThat(range.blocks()).singleElement().satisfies(block -> {
            assertThat(block.startLine()).isEqualTo(2);
            assertThat(block.endLine()).isEqualTo(3);
        });
    }

    private ReportOrganizationListRequest request(String sortBy, String direction) {
        return new ReportOrganizationListRequest(1, 20, null, null, sortBy, direction);
    }

    private ReportOrganizedInput input(String moduleKey, String moduleName, String fileKey, String path,
                                       String type, Integer line, String risk) {
        UUID inputId = UUID.randomUUID();
        Map<String, Object> snapshot = new java.util.LinkedHashMap<>();
        snapshot.put("issueTitle", type + " issue");
        snapshot.put("recommendationSummary", "fix");
        snapshot.put("sourceRefId", UUID.randomUUID());
        snapshot.put("sourceDetail", Map.of("filePath", path));
        return new ReportOrganizedInput(UUID.randomUUID(), inputId, "KB_FINDING", risk, moduleKey, moduleName,
                "DIRECTORY", "LOW", List.of(), fileKey, path, type, line, line, null, null, "symbol", "sha", line != null, snapshot);
    }

    private ReportOrganizedInput detailedInput(String moduleName, String moduleKey, String path, String type,
                                               String title, String symbol, String risk, Integer line,
                                               Object sourceRefId, Object sourceDetail) {
        Map<String, Object> snapshot = new java.util.LinkedHashMap<>();
        snapshot.put("issueTitle", title);
        snapshot.put("recommendationSummary", "fix");
        snapshot.put("sourceRefId", sourceRefId);
        snapshot.put("sourceDetail", sourceDetail);
        return new ReportOrganizedInput(UUID.randomUUID(), UUID.randomUUID(), "KB_FINDING", risk, moduleKey, moduleName,
                null, null, null, moduleKey, path, type, line, null, 1, 2, symbol, null, line != null, snapshot);
    }

    private ReportView report() {
        return new ReportView(reportId, projectId, UUID.randomUUID(), revisionId, ReportType.EVALUATION, TaskStatus.SUCCEEDED,
                "report", Map.of("organizationAvailable", true), "HIGH", UUID.randomUUID(), OffsetDateTime.now(), OffsetDateTime.now());
    }
}
