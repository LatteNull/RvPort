package cn.rvport.backend.migration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.when;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.analysis.SpecializedAnalysisFindingView;
import cn.rvport.backend.analysis.SpecializedAnalysisRepository;
import cn.rvport.backend.analysis.SpecializedAnalysisRunView;
import cn.rvport.backend.analysis.SpecializedAnalysisStatus;
import cn.rvport.backend.analysis.SpecializedAnalyzerType;
import cn.rvport.backend.dependency.DependencyAnalysisRepository;
import cn.rvport.backend.dependency.DependencyAnalysisResultItemView;
import cn.rvport.backend.dependency.DependencyConfidence;
import cn.rvport.backend.dependency.DependencyRiskLevel;
import cn.rvport.backend.dependency.DependencyTargetMatchStatus;
import cn.rvport.backend.dependency.DependencyType;
import cn.rvport.backend.kb.FindingView;
import cn.rvport.backend.kb.KbScanRepository;
import cn.rvport.backend.kb.KbScanView;
import cn.rvport.backend.task.TaskStatus;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class MigrationInputSourceResolverTests {
    @org.mockito.Mock private cn.rvport.backend.kb.KbScanContextService scanContextService;
    @Test
    void sourceAnchorsHandleMissingEmptyAndBlankEvidenceWithoutChangingIdentity() {
        UUID projectId = UUID.randomUUID(), revisionId = UUID.randomUUID(), id = UUID.randomUUID();
        var evidenceValues = new java.util.ArrayList<Map<String, Object>>();
        evidenceValues.add(null);
        evidenceValues.add(Map.of());
        evidenceValues.add(Map.of("anchor", " ", "snippet", "actual anchor"));
        for (var evidence : evidenceValues) {
            var finding = new FindingView(id, projectId, UUID.randomUUID(), revisionId, "RULE", "category", "high",
                    "title", "description", "a.c", 1, 1, "symbol", evidence, "fix", "fallback-fingerprint", "DETECTED", OffsetDateTime.now());
            when(kbScanRepository.findFinding(id)).thenReturn(Optional.of(finding));
            var candidate = resolver().resolve(projectId, revisionId, MigrationInputSourceType.KB_FINDING, id);
            assertThat(candidate.identityAnchor()).isEqualTo(evidence == null || evidence.isEmpty() ? "fallback-fingerprint" : "actual anchor");
        }
    }

    @Test
    void memoryOrderDefaultsToPendingAndKeepsHistoricalSelectionSeparate() {
        UUID projectId = UUID.randomUUID(), revisionId = UUID.randomUUID(), id = UUID.randomUUID();
        var raw = specializedFinding(id, projectId, revisionId, SpecializedAnalyzerType.MEMORY_ORDER, 1, 2, "candidate", "verify", "digest");
        when(specializedAnalysisRepository.findFinding(id)).thenReturn(Optional.of(raw));
        var resolver = specializedResolver();
        assertThat(resolver.resolve(projectId, revisionId, MigrationInputSourceType.MEMORY_ORDER_FINDING, id).initialStatus())
                .isEqualTo(MigrationInputStatus.CANDIDATE);
        var confirmed = ref(projectId, revisionId, MigrationInputSourceType.MEMORY_ORDER_FINDING, id);
        assertThat(resolver.detail(confirmed)).containsEntry("pendingVerification", true).containsEntry("findingKind", "INCONCLUSIVE");
        assertThat(confirmed.status()).isEqualTo(MigrationInputStatus.CONFIRMED);
        assertThat(raw.severity()).isEqualTo("high");
        assertThat(resolver().memoryOrderAnalysisSummary(projectId, revisionId)).containsEntry("analysisStatus", "UNAVAILABLE");
        assertThat(resolver.memoryOrderAnalysisSummary(projectId, revisionId)).containsEntry("analysisStatus", "UNAVAILABLE");
        var run = new SpecializedAnalysisRunView(UUID.randomUUID(), projectId, UUID.randomUUID(), SpecializedAnalyzerType.MEMORY_ORDER,
                revisionId, UUID.randomUUID(), "artifact-set", 1L, "tool", "request", "result", "policy",
                SpecializedAnalysisStatus.PARTIAL, "inconclusive", 2, Map.of("diagnosticCount", 0), null, null, null, null,
                0, 1, 0, UUID.randomUUID(), null, null, OffsetDateTime.now(), OffsetDateTime.now());
        when(specializedAnalysisRepository.latestPublished(projectId, revisionId, SpecializedAnalyzerType.MEMORY_ORDER)).thenReturn(Optional.of(run));
        assertThat(resolver.memoryOrderAnalysisSummary(projectId, revisionId)).containsEntry("analysisStatus", "PARTIAL")
                .containsEntry("diagnosticCount", null).containsEntry("diagnosticsAggregated", false);
        assertThat(run.summary()).containsEntry("diagnosticCount", 0);
    }

    @Mock
    private KbScanRepository kbScanRepository;


    @Mock
    private DependencyAnalysisRepository dependencyAnalysisRepository;

    @Mock
    private SpecializedAnalysisRepository specializedAnalysisRepository;

    @Test
    void resolvesAndDescribesSpecializedFindingsAcrossLocationShapes() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        UUID noLineId = UUID.randomUUID();
        UUID oneLineId = UUID.randomUUID();
        UUID rangeId = UUID.randomUUID();
        when(specializedAnalysisRepository.findFinding(noLineId)).thenReturn(Optional.of(
                specializedFinding(noLineId, projectId, revisionId, SpecializedAnalyzerType.FLOATING_POINT,
                        null, null, null, null, null)));
        when(specializedAnalysisRepository.findFinding(oneLineId)).thenReturn(Optional.of(
                specializedFinding(oneLineId, projectId, revisionId, SpecializedAnalyzerType.FLOATING_POINT,
                        7, null, "title", "suggestion", "digest")));
        when(specializedAnalysisRepository.findFinding(rangeId)).thenReturn(Optional.of(
                specializedFinding(rangeId, projectId, revisionId, SpecializedAnalyzerType.MEMORY_ORDER,
                        8, 10, "title", null, null)));

        MigrationInputSourceResolver resolver = specializedResolver();
        assertThat(resolver.resolve(projectId, revisionId, MigrationInputSourceType.FLOATING_POINT_FINDING, noLineId))
                .satisfies(candidate -> {
                    assertThat(candidate.issueTitle()).isEqualTo("FP001");
                    assertThat(candidate.locationLabel()).isEqualTo("unknown");
                    assertThat(candidate.recommendationSummary()).isEqualTo("test");
                    assertThat(candidate.identityAnchor()).isEqualTo("external-id");
                });
        assertThat(resolver.resolve(projectId, revisionId, MigrationInputSourceType.FLOATING_POINT_FINDING, oneLineId))
                .extracting(MigrationInputCandidate::locationLabel, MigrationInputCandidate::recommendationSummary)
                .containsExactly("src/main.c:7", "suggestion");
        assertThat(resolver.resolve(projectId, revisionId, MigrationInputSourceType.MEMORY_ORDER_FINDING, rangeId))
                .extracting(MigrationInputCandidate::locationLabel, MigrationInputCandidate::sourceType)
                .containsExactly("src/main.c:8-10", MigrationInputSourceType.MEMORY_ORDER_FINDING);
        assertThat(resolver.detail(ref(projectId, revisionId,
                MigrationInputSourceType.FLOATING_POINT_FINDING, oneLineId)))
                .containsEntry("findingCode", "FP001")
                .containsEntry("analysisDetail", Map.of("kind", "precision"));
    }

    @Test
    void specializedFindingsEnforceProjectRevisionTypeAndAvailability() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        UUID findingId = UUID.randomUUID();
        MigrationInputSourceResolver resolver = specializedResolver();

        when(specializedAnalysisRepository.findFinding(findingId)).thenReturn(Optional.empty());
        assertThatThrownBy(() -> resolver.resolve(projectId, revisionId,
                MigrationInputSourceType.FLOATING_POINT_FINDING, findingId))
                .isInstanceOf(ApiException.class).extracting("code")
                .isEqualTo("MIGRATION_INPUT_SOURCE_NOT_FOUND");

        when(specializedAnalysisRepository.findFinding(findingId)).thenReturn(Optional.of(
                specializedFinding(findingId, UUID.randomUUID(), revisionId,
                        SpecializedAnalyzerType.FLOATING_POINT, 1, 1, "title", "fix", "digest")));
        assertThatThrownBy(() -> resolver.resolve(projectId, revisionId,
                MigrationInputSourceType.FLOATING_POINT_FINDING, findingId))
                .isInstanceOf(ApiException.class).extracting("code")
                .isEqualTo("MIGRATION_INPUT_SOURCE_NOT_FOUND");

        when(specializedAnalysisRepository.findFinding(findingId)).thenReturn(Optional.of(
                specializedFinding(findingId, projectId, UUID.randomUUID(),
                        SpecializedAnalyzerType.FLOATING_POINT, 1, 1, "title", "fix", "digest")));
        assertThatThrownBy(() -> resolver.resolve(projectId, revisionId,
                MigrationInputSourceType.FLOATING_POINT_FINDING, findingId))
                .isInstanceOf(ApiException.class).extracting("code")
                .isEqualTo("MIGRATION_INPUT_SOURCE_REVISION_MISMATCH");

        when(specializedAnalysisRepository.findFinding(findingId)).thenReturn(Optional.of(
                specializedFinding(findingId, projectId, revisionId,
                        SpecializedAnalyzerType.MEMORY_ORDER, 1, 1, "title", "fix", "digest")));
        assertThatThrownBy(() -> resolver.resolve(projectId, revisionId,
                MigrationInputSourceType.FLOATING_POINT_FINDING, findingId))
                .isInstanceOf(ApiException.class).extracting("code")
                .isEqualTo("MIGRATION_INPUT_SOURCE_REVISION_MISMATCH");

        assertThat(resolver().latestSourceRefIds(projectId, revisionId,
                MigrationInputSourceType.FLOATING_POINT_FINDING)).isEmpty();
        assertThatThrownBy(() -> resolver().detail(ref(projectId, revisionId,
                MigrationInputSourceType.FLOATING_POINT_FINDING, findingId)))
                .isInstanceOf(ApiException.class).extracting("code")
                .isEqualTo("MIGRATION_INPUT_SOURCE_NOT_FOUND");
    }

    @Test
    void latestSpecializedFindingIdsUsePublishedRunForEachAnalyzer() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        UUID runId = UUID.randomUUID();
        UUID findingId = UUID.randomUUID();
        SpecializedAnalysisRunView run = new SpecializedAnalysisRunView(
                runId, projectId, UUID.randomUUID(), SpecializedAnalyzerType.FLOATING_POINT, revisionId,
                UUID.randomUUID(), "artifact-set", 1L, "tool", "request", "result", "policy",
                SpecializedAnalysisStatus.COMPLETE, "PASS", 0, Map.of(), null, null, null, null,
                1, 0, 0, UUID.randomUUID(), null, null, OffsetDateTime.now(), OffsetDateTime.now());
        when(specializedAnalysisRepository.latestPublished(
                projectId, revisionId, SpecializedAnalyzerType.FLOATING_POINT)).thenReturn(Optional.of(run));
        when(specializedAnalysisRepository.listFindingIds(runId)).thenReturn(List.of(findingId));
        when(specializedAnalysisRepository.latestPublished(
                projectId, revisionId, SpecializedAnalyzerType.MEMORY_ORDER)).thenReturn(Optional.empty());

        assertThat(specializedResolver().latestSourceRefIds(projectId, revisionId,
                MigrationInputSourceType.FLOATING_POINT_FINDING)).containsExactly(findingId);
        assertThat(specializedResolver().latestSourceRefIds(projectId, revisionId,
                MigrationInputSourceType.MEMORY_ORDER_FINDING)).isEmpty();
    }

    @Test
    void resolvesKbFindingWithRelativePathAndLineRange() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID findingId = UUID.randomUUID();
        when(kbScanRepository.findFinding(findingId)).thenReturn(Optional.of(finding(projectId, sourceRevisionId, findingId, 10, 12)));

        MigrationInputCandidate candidate = resolver().resolve(projectId, sourceRevisionId, MigrationInputSourceType.KB_FINDING, findingId);

        assertThat(candidate.issueTitle()).isEqualTo("AVX intrinsic");
        assertThat(candidate.detectedLevel()).isEqualTo("HIGH");
        assertThat(candidate.initialStatus()).isEqualTo(MigrationInputStatus.CONFIRMED);
        assertThat(candidate.locationLabel()).isEqualTo("src/main.c:10-12");
        assertThat(candidate.recommendationSummary()).isEqualTo("replace intrinsic");
    }

    @Test
    void lowKbFindingDefaultsToCandidate() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID findingId = UUID.randomUUID();
        when(kbScanRepository.findFinding(findingId)).thenReturn(Optional.of(finding(projectId, sourceRevisionId, findingId, "low", 1, 1)));

        MigrationInputCandidate candidate = resolver().resolve(projectId, sourceRevisionId, MigrationInputSourceType.KB_FINDING, findingId);

        assertThat(candidate.detectedLevel()).isEqualTo("LOW");
        assertThat(candidate.initialStatus()).isEqualTo(MigrationInputStatus.CANDIDATE);
    }

    @Test
    void resolvesKbFindingWithoutLineAsPathOnly() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID findingId = UUID.randomUUID();
        when(kbScanRepository.findFinding(findingId)).thenReturn(Optional.of(finding(projectId, sourceRevisionId, findingId, null, null)));

        MigrationInputCandidate candidate = resolver().resolve(projectId, sourceRevisionId, MigrationInputSourceType.KB_FINDING, findingId);

        assertThat(candidate.locationLabel()).isEqualTo("src/main.c");
    }

    @Test
    void resolvesKbFindingWithOnlyStartLineAndRejectsForeignProject() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID findingId = UUID.randomUUID();
        when(kbScanRepository.findFinding(findingId)).thenReturn(Optional.of(
                finding(projectId, sourceRevisionId, findingId, 7, null)));
        assertThat(resolver().resolve(projectId, sourceRevisionId,
                MigrationInputSourceType.KB_FINDING, findingId).locationLabel()).isEqualTo("src/main.c:7");

        UUID foreignId = UUID.randomUUID();
        when(kbScanRepository.findFinding(foreignId)).thenReturn(Optional.of(
                finding(UUID.randomUUID(), sourceRevisionId, foreignId, 1, 1)));
        assertThatThrownBy(() -> resolver().resolve(projectId, sourceRevisionId,
                MigrationInputSourceType.KB_FINDING, foreignId))
                .isInstanceOf(ApiException.class).extracting("code")
                .isEqualTo("MIGRATION_INPUT_SOURCE_NOT_FOUND");
    }

    @Test
    void rejectsKbFindingFromAnotherSourceRevision() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID findingId = UUID.randomUUID();
        when(kbScanRepository.findFinding(findingId)).thenReturn(Optional.of(finding(projectId, UUID.randomUUID(), findingId, 1, 1)));

        assertThatThrownBy(() -> resolver().resolve(projectId, sourceRevisionId, MigrationInputSourceType.KB_FINDING, findingId))
                .isInstanceOf(ApiException.class)
                .hasMessageContaining("源码版本");
    }

    @Test
    void resolvesDependencyResultWithCombinedLevelAndDefaultStatus() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID itemId = UUID.randomUUID();
        when(dependencyAnalysisRepository.findResultItem(itemId)).thenReturn(Optional.of(dependencyItem(projectId, sourceRevisionId, itemId, DependencyRiskLevel.LOW)));

        MigrationInputCandidate candidate = resolver().resolve(projectId, sourceRevisionId, MigrationInputSourceType.DEPENDENCY_RESULT, itemId);

        assertThat(candidate.detectedLevel()).isEqualTo("LOW/TARGET_NEWER");
        assertThat(candidate.locationLabel()).isEqualTo("build:gcc");
        assertThat(candidate.initialStatus()).isEqualTo(MigrationInputStatus.CANDIDATE);
    }

    @Test
    void latestSourceRefIdsUseLatestSuccessfulRuns() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID kbRunId = UUID.randomUUID();
        UUID findingId = UUID.randomUUID();
        UUID resultItemId = UUID.randomUUID();
        when(scanContextService.currentRun(projectId, sourceRevisionId)).thenReturn(Optional.of(kbRun(projectId, sourceRevisionId, kbRunId)));
        when(kbScanRepository.listFindingIds(kbRunId)).thenReturn(List.of(findingId));

        assertThat(resolver().latestSourceRefIds(projectId, sourceRevisionId, MigrationInputSourceType.KB_FINDING)).containsExactly(findingId);
    }

    @Test
    void resolvesRejectMissingAndForeignSourcesForEverySourceType() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        UUID id = UUID.randomUUID();
        when(kbScanRepository.findFinding(id)).thenReturn(Optional.empty());
        assertThatThrownBy(() -> resolver().resolve(projectId, revisionId, MigrationInputSourceType.KB_FINDING, id))
                .isInstanceOf(ApiException.class).extracting("code").isEqualTo("MIGRATION_INPUT_SOURCE_NOT_FOUND");


        UUID dependencyId = UUID.randomUUID();
        when(dependencyAnalysisRepository.findResultItem(dependencyId)).thenReturn(Optional.empty());
        assertThatThrownBy(() -> resolver().resolve(projectId, revisionId, MigrationInputSourceType.DEPENDENCY_RESULT, dependencyId))
                .isInstanceOf(ApiException.class).extracting("code").isEqualTo("MIGRATION_INPUT_SOURCE_NOT_FOUND");

        when(dependencyAnalysisRepository.findResultItem(dependencyId)).thenReturn(Optional.of(
                dependencyItem(UUID.randomUUID(), revisionId, dependencyId, DependencyRiskLevel.HIGH)));
        assertThatThrownBy(() -> resolver().resolve(projectId, revisionId, MigrationInputSourceType.DEPENDENCY_RESULT, dependencyId))
                .isInstanceOf(ApiException.class).extracting("code").isEqualTo("MIGRATION_INPUT_SOURCE_NOT_FOUND");

        when(dependencyAnalysisRepository.findResultItem(dependencyId)).thenReturn(Optional.of(
                dependencyItem(projectId, UUID.randomUUID(), dependencyId, DependencyRiskLevel.HIGH)));
        assertThatThrownBy(() -> resolver().resolve(projectId, revisionId, MigrationInputSourceType.DEPENDENCY_RESULT, dependencyId))
                .isInstanceOf(ApiException.class).extracting("code").isEqualTo("MIGRATION_INPUT_SOURCE_REVISION_MISMATCH");
    }

    @Test
    void detailReturnsCompleteMapsForEverySourceAndRejectsMissingItems() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        FindingView finding = finding(projectId, revisionId, UUID.randomUUID(), 2, 3);
        DependencyAnalysisResultItemView dependency = dependencyItem(projectId, revisionId, UUID.randomUUID(), DependencyRiskLevel.MEDIUM);
        when(kbScanRepository.findFinding(finding.id())).thenReturn(Optional.of(finding));
        when(dependencyAnalysisRepository.findResultItem(dependency.id())).thenReturn(Optional.of(dependency));

        assertThat(resolver().detail(ref(projectId, revisionId, MigrationInputSourceType.KB_FINDING, finding.id())))
                .containsEntry("ruleId", "AVX001").containsEntry("lineStart", 2);
        assertThat(resolver().detail(ref(projectId, revisionId, MigrationInputSourceType.DEPENDENCY_RESULT, dependency.id())))
                .containsEntry("dependencyName", "gcc")
                .containsEntry("dependencyType", DependencyType.BUILD_TOOL)
                .containsEntry("sourceProviderPackage", "gcc")
                .containsEntry("sourceProviderVersion", "12.3")
                .containsEntry("targetProviderPackage", "gcc")
                .containsEntry("targetProviderVersion", "13.2")
                .containsEntry("providerVersionStatus", "TARGET_NEWER");

        UUID missing = UUID.randomUUID();
        when(kbScanRepository.findFinding(missing)).thenReturn(Optional.empty());
        assertThatThrownBy(() -> resolver().detail(ref(projectId, revisionId, MigrationInputSourceType.KB_FINDING, missing)))
                .isInstanceOf(ApiException.class);
        when(dependencyAnalysisRepository.findResultItem(missing)).thenReturn(Optional.empty());
        assertThatThrownBy(() -> resolver().detail(ref(projectId, revisionId, MigrationInputSourceType.DEPENDENCY_RESULT, missing)))
                .isInstanceOf(ApiException.class);
    }

    @Test
    void derivesLocationsForEveryDependencyKindAndPreservesExplicitLocation() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        Map<DependencyType, String> expected = Map.of(
                DependencyType.BUILD_TOOL, "build:gcc",
                DependencyType.BUILD_PACKAGE, "package:gcc@12.3",
                DependencyType.TEST_PACKAGE, "package:gcc@12.3",
                DependencyType.LINK_LIBRARY, "lib:gcc",
                DependencyType.RUNTIME_LIBRARY, "lib:gcc",
                DependencyType.TEST_TOOL, "test:gcc");
        for (var entry : expected.entrySet()) {
            UUID id = UUID.randomUUID();
            DependencyAnalysisResultItemView item = dependencyItem(projectId, revisionId, id,
                    DependencyRiskLevel.MEDIUM, entry.getKey(), null, "12.3");
            when(dependencyAnalysisRepository.findResultItem(id)).thenReturn(Optional.of(item));
            assertThat(resolver().resolve(projectId, revisionId, MigrationInputSourceType.DEPENDENCY_RESULT, id).locationLabel())
                    .isEqualTo(entry.getValue());
        }

        UUID explicitId = UUID.randomUUID();
        when(dependencyAnalysisRepository.findResultItem(explicitId)).thenReturn(Optional.of(
                dependencyItem(projectId, revisionId, explicitId, DependencyRiskLevel.LOW,
                        DependencyType.BUILD_TOOL, "custom/location", null)));
        assertThat(resolver().resolve(projectId, revisionId, MigrationInputSourceType.DEPENDENCY_RESULT, explicitId).locationLabel())
                .isEqualTo("custom/location");

        UUID blankId = UUID.randomUUID();
        when(dependencyAnalysisRepository.findResultItem(blankId)).thenReturn(Optional.of(
                dependencyItem(projectId, revisionId, blankId, DependencyRiskLevel.LOW,
                        DependencyType.BUILD_TOOL, "  ", null)));
        assertThat(resolver().resolve(projectId, revisionId,
                MigrationInputSourceType.DEPENDENCY_RESULT, blankId).locationLabel()).isEqualTo("build:gcc");
    }

    @Test
    void latestSourceIdsReturnEmptyForMissingOrUnsuccessfulRunsAndResolveDependencyRun() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        when(scanContextService.currentRun(projectId, revisionId)).thenReturn(Optional.empty());
        assertThat(resolver().latestSourceRefIds(projectId, revisionId, MigrationInputSourceType.KB_FINDING)).isEmpty();

        UUID runId = UUID.randomUUID();
        UUID itemId = UUID.randomUUID();
        when(dependencyAnalysisRepository.findLatestSucceededRun(projectId, revisionId)).thenReturn(Optional.of(
                new cn.rvport.backend.dependency.DependencyAnalysisView(runId, projectId, UUID.randomUUID(), revisionId,
                        UUID.randomUUID(), UUID.randomUUID(), 1L, TaskStatus.SUCCEEDED, Map.of(), null, null, null, null)));
        when(dependencyAnalysisRepository.listResultItemIds(runId)).thenReturn(List.of(itemId));
        assertThat(resolver().latestSourceRefIds(projectId, revisionId, MigrationInputSourceType.DEPENDENCY_RESULT))
                .containsExactly(itemId);

        when(dependencyAnalysisRepository.findLatestSucceededRun(projectId, revisionId)).thenReturn(Optional.of(
                new cn.rvport.backend.dependency.DependencyAnalysisView(UUID.randomUUID(), projectId,
                        UUID.randomUUID(), revisionId, UUID.randomUUID(), UUID.randomUUID(), 1L,
                        TaskStatus.FAILED, Map.of(), null, null, null, null)));
        assertThat(resolver().latestSourceRefIds(projectId, revisionId,
                MigrationInputSourceType.DEPENDENCY_RESULT)).isEmpty();
    }

    private MigrationInputSourceResolver resolver() {
        MigrationInputSourceResolver service = new MigrationInputSourceResolver(kbScanRepository, dependencyAnalysisRepository);
        org.springframework.test.util.ReflectionTestUtils.setField(service, "scanContextService", scanContextService);
        return service;
    }

    @Test
    void blankPackageVersionDoesNotCreateAnEmptyVersionSuffix() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        UUID itemId = UUID.randomUUID();
        when(dependencyAnalysisRepository.findResultItem(itemId)).thenReturn(Optional.of(
                dependencyItem(projectId, revisionId, itemId, DependencyRiskLevel.LOW,
                        DependencyType.BUILD_PACKAGE, null, "  ")));
        MigrationInputCandidate candidate = resolver().resolve(projectId, revisionId,
                MigrationInputSourceType.DEPENDENCY_RESULT, itemId);
        assertThat(candidate.locationLabel()).isEqualTo("package:gcc");
        assertThat(candidate.initialStatus()).isEqualTo(MigrationInputStatus.CANDIDATE);
    }

    private MigrationInputSourceResolver specializedResolver() {
        MigrationInputSourceResolver service = new MigrationInputSourceResolver(kbScanRepository, dependencyAnalysisRepository,
                null, specializedAnalysisRepository);
        org.springframework.test.util.ReflectionTestUtils.setField(service, "scanContextService", scanContextService);
        return service;
    }

    private SpecializedAnalysisFindingView specializedFinding(
            UUID id,
            UUID projectId,
            UUID revisionId,
            SpecializedAnalyzerType analyzerType,
            Integer startLine,
            Integer endLine,
            String title,
            String suggestion,
            String digest
    ) {
        return new SpecializedAnalysisFindingView(
                id, UUID.randomUUID(), projectId, revisionId, analyzerType, "external-id", "kind", "FP001",
                "category", "high", "HIGH", "DETECTED", title, "title-en", "message", "message-en",
                suggestion, "suggestion-en", "test", "test-en", startLine == null ? null : "src/main.c",
                startLine, 1, endLine, 2, true, digest, Map.of("kind", "precision"), OffsetDateTime.now());
    }

    private FindingView finding(UUID projectId, UUID sourceRevisionId, UUID findingId, Integer lineStart, Integer lineEnd) {
        return finding(projectId, sourceRevisionId, findingId, "high", lineStart, lineEnd);
    }

    private FindingView finding(UUID projectId, UUID sourceRevisionId, UUID findingId, String severity, Integer lineStart, Integer lineEnd) {
        return new FindingView(
                findingId,
                projectId,
                UUID.randomUUID(),
                sourceRevisionId,
                "AVX001",
                "portability",
                severity,
                "AVX intrinsic",
                "uses x86 intrinsic",
                "src/main.c",
                lineStart,
                lineEnd,
                "_mm_add_epi32",
                Map.of("kind", "intrinsic"),
                "replace intrinsic",
                "fp",
                "DETECTED",
                OffsetDateTime.now()
        );
    }

    private DependencyAnalysisResultItemView dependencyItem(UUID projectId, UUID sourceRevisionId, UUID itemId, DependencyRiskLevel riskLevel) {
        return dependencyItem(projectId, sourceRevisionId, itemId, riskLevel, DependencyType.BUILD_TOOL, null, null);
    }

    private DependencyAnalysisResultItemView dependencyItem(UUID projectId, UUID sourceRevisionId, UUID itemId,
                                                              DependencyRiskLevel riskLevel, DependencyType type,
                                                              String locationLabel, String version) {
        return new DependencyAnalysisResultItemView(
                itemId,
                projectId,
                sourceRevisionId,
                UUID.randomUUID(),
                UUID.randomUUID(),
                type,
                "gcc",
                version,
                "gcc",
                "12.3",
                "12.3",
                "gcc",
                "13.2",
                "13.2",
                "TARGET_NEWER",
                "PACKAGE_OWNER",
                DependencyTargetMatchStatus.TARGET_NEWER,
                riskLevel,
                locationLabel,
                "confirm gcc compatibility",
                DependencyConfidence.HIGH,
                Map.of(),
                OffsetDateTime.now()
        );
    }

    private MigrationInputRefView ref(UUID projectId, UUID sourceRevisionId, MigrationInputSourceType sourceType, UUID sourceRefId) {
        return new MigrationInputRefView(UUID.randomUUID(), UUID.randomUUID(), projectId, sourceRevisionId,
                "issue", sourceType, sourceRefId, "HIGH", "location", "fix", "rule", "path", "symbol",
                "anchor", "fingerprint", MigrationInputStatus.CONFIRMED, null, OffsetDateTime.now(), null);
    }

    private KbScanView kbRun(UUID projectId, UUID sourceRevisionId, UUID runId) {
        return new KbScanView(runId, projectId, UUID.randomUUID(), sourceRevisionId, null, Map.of(), TaskStatus.SUCCEEDED, Map.of(), OffsetDateTime.now(), OffsetDateTime.now());
    }

}
