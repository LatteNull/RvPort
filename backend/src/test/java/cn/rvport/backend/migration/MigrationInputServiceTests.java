package cn.rvport.backend.migration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.project.ProjectAccessService;
import cn.rvport.backend.source.SourceRevisionType;
import cn.rvport.backend.source.SourceRevisionView;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpStatus;

@ExtendWith(MockitoExtension.class)
class MigrationInputServiceTests {

    @Mock
    private MigrationInputRepository migrationInputRepository;

    @Mock
    private MigrationInputSourceResolver sourceResolver;

    @Mock
    private ProjectAccessService projectAccessService;

    @Test
    void importsMultipleSourceRefsAndReportsCreatedAndSkippedCounts() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        UUID inputSetId = UUID.randomUUID();
        UUID firstRefId = UUID.randomUUID();
        UUID secondRefId = UUID.randomUUID();
        MigrationInputCandidate first = candidate(projectId, sourceRevisionId, firstRefId, "first");
        MigrationInputCandidate second = candidate(projectId, sourceRevisionId, secondRefId, "second");
        MigrationInputRefView created = ref(projectId, sourceRevisionId, firstRefId, "first", MigrationInputStatus.CANDIDATE);
        when(projectAccessService.requireSourceRevisionAccess(projectId, sourceRevisionId, actorId, false))
                .thenReturn(revision(projectId, sourceRevisionId));
        when(migrationInputRepository.ensureActiveSet(projectId, sourceRevisionId)).thenReturn(inputSetId);
        when(sourceResolver.resolve(projectId, sourceRevisionId, MigrationInputSourceType.KB_FINDING, firstRefId)).thenReturn(first);
        when(sourceResolver.resolve(projectId, sourceRevisionId, MigrationInputSourceType.KB_FINDING, secondRefId)).thenReturn(second);
        when(migrationInputRepository.insertCandidates(inputSetId, List.of(first, second)))
                .thenReturn(new MigrationInputRepository.InsertResult(List.of(created), 1));

        MigrationInputImportResponse response = service().importRefs(
                projectId,
                sourceRevisionId,
                new MigrationInputImportRequest(MigrationInputSourceType.KB_FINDING, List.of(firstRefId, secondRefId)),
                actorId,
                false
        );

        assertThat(response.requested()).isEqualTo(2);
        assertThat(response.created()).isEqualTo(1);
        assertThat(response.skipped()).isEqualTo(1);
        assertThat(response.items()).extracting(MigrationInputResponse::issueTitle).containsExactly("first");
    }

    @Test
    void rejectsEmptyImportList() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        when(projectAccessService.requireSourceRevisionAccess(projectId, sourceRevisionId, actorId, false))
                .thenReturn(revision(projectId, sourceRevisionId));

        assertThatThrownBy(() -> service().importRefs(
                projectId,
                sourceRevisionId,
                new MigrationInputImportRequest(MigrationInputSourceType.KB_FINDING, List.of()),
                actorId,
                false
        ))
                .isInstanceOf(ApiException.class)
                .extracting("status")
                .isEqualTo(HttpStatus.BAD_REQUEST);
    }

    @Test
    void propagatesCrossRevisionSourceValidationFailure() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        UUID inputSetId = UUID.randomUUID();
        UUID refId = UUID.randomUUID();
        when(projectAccessService.requireSourceRevisionAccess(projectId, sourceRevisionId, actorId, false))
                .thenReturn(revision(projectId, sourceRevisionId));
        when(migrationInputRepository.ensureActiveSet(projectId, sourceRevisionId)).thenReturn(inputSetId);
        when(sourceResolver.resolve(projectId, sourceRevisionId, MigrationInputSourceType.KB_FINDING, refId))
                .thenThrow(new ApiException(HttpStatus.BAD_REQUEST, "MIGRATION_INPUT_SOURCE_REVISION_MISMATCH", "KB finding 不属于当前源码版本"));

        assertThatThrownBy(() -> service().importRefs(
                projectId,
                sourceRevisionId,
                new MigrationInputImportRequest(MigrationInputSourceType.KB_FINDING, List.of(refId)),
                actorId,
                false
        ))
                .isInstanceOf(ApiException.class)
                .hasMessageContaining("KB finding");
    }

    @Test
    void autoMergeIsDeprecated() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        when(projectAccessService.requireSourceRevisionAccess(projectId, sourceRevisionId, actorId, false))
                .thenReturn(revision(projectId, sourceRevisionId));

        assertThatThrownBy(() -> service().autoMerge(
                projectId,
                sourceRevisionId,
                new MigrationInputAutoMergeRequest(List.of(MigrationInputSourceType.KB_FINDING)),
                actorId,
                false
        ))
                .isInstanceOf(ApiException.class)
                .hasMessageContaining("自动合并已废弃")
                .extracting("status")
                .isEqualTo(HttpStatus.BAD_REQUEST);
    }

    @Test
    void syncSourceRefsImportsWithoutUserAccessCheckForWorkers() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID inputSetId = UUID.randomUUID();
        UUID refId = UUID.randomUUID();
        MigrationInputCandidate candidate = candidate(projectId, sourceRevisionId, refId, "dependency", MigrationInputSourceType.DEPENDENCY_RESULT);
        MigrationInputRefView created = ref(projectId, sourceRevisionId, refId, "dependency", MigrationInputStatus.CONFIRMED);
        when(migrationInputRepository.ensureActiveSet(projectId, sourceRevisionId)).thenReturn(inputSetId);
        when(sourceResolver.resolve(projectId, sourceRevisionId, MigrationInputSourceType.DEPENDENCY_RESULT, refId)).thenReturn(candidate);
        when(migrationInputRepository.insertCandidates(inputSetId, List.of(candidate)))
                .thenReturn(new MigrationInputRepository.InsertResult(List.of(created), 0));

        MigrationInputRepository.InsertResult result = service().syncSourceRefs(
                projectId,
                sourceRevisionId,
                MigrationInputSourceType.DEPENDENCY_RESULT,
                List.of(refId, refId)
        );

        assertThat(result.createdItems()).containsExactly(created);
        assertThat(result.skipped()).isZero();
        verify(migrationInputRepository).deleteBySourceType(projectId, sourceRevisionId, MigrationInputSourceType.DEPENDENCY_RESULT);
    }

    @Test
    void syncSourceRefsReplacesExistingRefsForSameSourceType() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID inputSetId = UUID.randomUUID();
        UUID refId = UUID.randomUUID();
        MigrationInputCandidate candidate = candidate(projectId, sourceRevisionId, refId, "latest", MigrationInputSourceType.DEPENDENCY_RESULT);
        when(migrationInputRepository.ensureActiveSet(projectId, sourceRevisionId)).thenReturn(inputSetId);
        when(sourceResolver.resolve(projectId, sourceRevisionId, MigrationInputSourceType.DEPENDENCY_RESULT, refId)).thenReturn(candidate);
        when(migrationInputRepository.insertCandidates(inputSetId, List.of(candidate)))
                .thenReturn(new MigrationInputRepository.InsertResult(List.of(), 0));

        service().syncSourceRefs(projectId, sourceRevisionId, MigrationInputSourceType.DEPENDENCY_RESULT, List.of(refId));

        org.mockito.InOrder order = org.mockito.Mockito.inOrder(migrationInputRepository);
        order.verify(migrationInputRepository).deleteBySourceType(projectId, sourceRevisionId, MigrationInputSourceType.DEPENDENCY_RESULT);
        order.verify(migrationInputRepository).ensureActiveSet(projectId, sourceRevisionId);
        order.verify(migrationInputRepository).insertCandidates(inputSetId, List.of(candidate));
    }

    @Test
    void syncSourceRefsClearsSameSourceTypeWhenLatestResultIsEmpty() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();

        MigrationInputRepository.InsertResult result = service().syncSourceRefs(
                projectId,
                sourceRevisionId,
                MigrationInputSourceType.KB_FINDING,
                List.of()
        );

        assertThat(result.createdItems()).isEmpty();
        assertThat(result.skipped()).isZero();
        verify(migrationInputRepository).deleteBySourceType(projectId, sourceRevisionId, MigrationInputSourceType.KB_FINDING);
        org.mockito.Mockito.verify(migrationInputRepository, org.mockito.Mockito.never()).ensureActiveSet(projectId, sourceRevisionId);
        org.mockito.Mockito.verify(migrationInputRepository, org.mockito.Mockito.never()).insertCandidates(org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any());
    }

    @Test
    void syncSourceRefsDoesNotInheritManualExclusionFromPreviousRun() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID inputSetId = UUID.randomUUID();
        UUID latestRefId = UUID.randomUUID();
        MigrationInputCandidate latestCandidate = candidate(
                projectId,
                sourceRevisionId,
                latestRefId,
                "latest medium finding",
                MigrationInputSourceType.KB_FINDING,
                "MEDIUM"
        );
        MigrationInputRefView created = ref(projectId, sourceRevisionId, latestRefId, "latest medium finding", MigrationInputStatus.CONFIRMED);
        when(migrationInputRepository.ensureActiveSet(projectId, sourceRevisionId)).thenReturn(inputSetId);
        when(sourceResolver.resolve(projectId, sourceRevisionId, MigrationInputSourceType.KB_FINDING, latestRefId)).thenReturn(latestCandidate);
        when(migrationInputRepository.insertCandidates(inputSetId, List.of(latestCandidate)))
                .thenReturn(new MigrationInputRepository.InsertResult(List.of(created), 0));

        MigrationInputRepository.InsertResult result = service().syncSourceRefs(
                projectId,
                sourceRevisionId,
                MigrationInputSourceType.KB_FINDING,
                List.of(latestRefId)
        );

        assertThat(result.createdItems()).containsExactly(created);
        assertThat(result.createdItems().getFirst().status()).isEqualTo(MigrationInputStatus.CONFIRMED);
        verify(migrationInputRepository).deleteBySourceType(projectId, sourceRevisionId, MigrationInputSourceType.KB_FINDING);
        verify(migrationInputRepository).insertCandidates(inputSetId, List.of(latestCandidate));
        org.mockito.Mockito.verify(migrationInputRepository, org.mockito.Mockito.never()).confirmedRefs(projectId, sourceRevisionId);
    }

    @Test
    void returnsOnlyConfirmedRefsForReportConsumers() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        MigrationInputRefView confirmed = ref(projectId, sourceRevisionId, UUID.randomUUID(), "confirmed", MigrationInputStatus.CONFIRMED);
        when(projectAccessService.requireSourceRevisionAccess(projectId, sourceRevisionId, actorId, false))
                .thenReturn(revision(projectId, sourceRevisionId));
        when(migrationInputRepository.listAll(projectId, sourceRevisionId)).thenReturn(List.of(confirmed));

        List<MigrationInputRefView> refs = service().confirmedRefs(projectId, sourceRevisionId, actorId, false);

        assertThat(refs).containsExactly(confirmed);
        verify(migrationInputRepository).listAll(projectId, sourceRevisionId);
    }

    @Test
    void currentRefsForSystemFiltersStaleDependencyRefsFromPreviousRun() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID staleRefId = UUID.randomUUID();
        UUID latestRefId = UUID.randomUUID();
        MigrationInputRefView staleConfirmed = dependencyRef(projectId, sourceRevisionId, staleRefId,
                "glibc 依赖可用性分析", MigrationInputStatus.CONFIRMED, "HIGH/MISSING", "BUILD_PACKAGE", "glibc");
        MigrationInputRefView latestCandidate = dependencyRef(projectId, sourceRevisionId, latestRefId,
                "glibc 依赖可用性分析", MigrationInputStatus.CANDIDATE, "INFO/TARGET_INSTALLED", "BUILD_PACKAGE", "glibc");
        when(migrationInputRepository.listAll(projectId, sourceRevisionId)).thenReturn(List.of(staleConfirmed, latestCandidate));
        when(sourceResolver.latestSourceRefIds(projectId, sourceRevisionId, MigrationInputSourceType.DEPENDENCY_RESULT))
                .thenReturn(List.of(latestRefId));

        List<MigrationInputRefView> refs = service().currentRefsForSystem(projectId, sourceRevisionId);

        assertThat(refs).containsExactly(latestCandidate);
    }

    @Test
    void currentRefsForSystemDeduplicatesSameDependencyButKeepsDistinctLibraries() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID buildGccId = UUID.randomUUID();
        UUID execveGccId = UUID.randomUUID();
        UUID libgccId = UUID.randomUUID();
        UUID libgccSId = UUID.randomUUID();
        MigrationInputRefView buildGcc = dependencyRef(projectId, sourceRevisionId, buildGccId,
                "gcc 依赖可用性分析", MigrationInputStatus.CANDIDATE, "LOW/TARGET_NEWER", "BUILD_TOOL", "gcc");
        MigrationInputRefView execveGcc = dependencyRef(projectId, sourceRevisionId, execveGccId,
                "gcc 依赖可用性分析", MigrationInputStatus.CANDIDATE, "INFO/TARGET_INSTALLED", "BUILD_TOOL", "gcc");
        MigrationInputRefView libgcc = dependencyRef(projectId, sourceRevisionId, libgccId,
                "libgcc.so 依赖可用性分析", MigrationInputStatus.CANDIDATE, "MEDIUM/REPO_AVAILABLE", "LINK_LIBRARY", "libgcc.so");
        MigrationInputRefView libgccS = dependencyRef(projectId, sourceRevisionId, libgccSId,
                "libgcc_s.so 依赖可用性分析", MigrationInputStatus.CANDIDATE, "MEDIUM/REPO_AVAILABLE", "LINK_LIBRARY", "libgcc_s.so");
        when(migrationInputRepository.listAll(projectId, sourceRevisionId)).thenReturn(List.of(buildGcc, execveGcc, libgcc, libgccS));
        when(sourceResolver.latestSourceRefIds(projectId, sourceRevisionId, MigrationInputSourceType.DEPENDENCY_RESULT))
                .thenReturn(List.of(buildGccId, execveGccId, libgccId, libgccSId));

        List<MigrationInputRefView> refs = service().currentRefsForSystem(projectId, sourceRevisionId);

        assertThat(refs).containsExactly(buildGcc, libgcc, libgccS);
    }

    @Test
    void currentConfirmedRefsForSystemHonorsExcludedDuplicateBeforeFilteringConfirmed() {
        UUID projectId = UUID.randomUUID();
        UUID sourceRevisionId = UUID.randomUUID();
        UUID excludedId = UUID.randomUUID();
        UUID confirmedDuplicateId = UUID.randomUUID();
        MigrationInputRefView excluded = dependencyRef(projectId, sourceRevisionId, excludedId,
                "glibc 依赖可用性分析", MigrationInputStatus.EXCLUDED, "HIGH/MISSING", "BUILD_PACKAGE", "glibc");
        MigrationInputRefView confirmedDuplicate = dependencyRef(projectId, sourceRevisionId, confirmedDuplicateId,
                "glibc 依赖可用性分析", MigrationInputStatus.CONFIRMED, "MEDIUM/REPO_AVAILABLE", "BUILD_PACKAGE", "glibc");
        when(migrationInputRepository.listAll(projectId, sourceRevisionId)).thenReturn(List.of(confirmedDuplicate, excluded));
        when(sourceResolver.latestSourceRefIds(projectId, sourceRevisionId, MigrationInputSourceType.DEPENDENCY_RESULT))
                .thenReturn(List.of(excludedId, confirmedDuplicateId));

        List<MigrationInputRefView> refs = service().currentConfirmedRefsForSystem(projectId, sourceRevisionId);

        assertThat(refs).isEmpty();
    }

    @Test
    void listFiltersKeywordsLevelsStatusesAndPaginates() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        MigrationInputRefView first = ref(projectId, revisionId, UUID.randomUUID(), "Alpha issue", MigrationInputStatus.CONFIRMED);
        MigrationInputRefView second = dependencyRef(projectId, revisionId, UUID.randomUUID(), "Beta issue",
                MigrationInputStatus.CANDIDATE, "LOW/TARGET_NEWER", "BUILD_TOOL", "gcc");
        when(migrationInputRepository.listAll(projectId, revisionId)).thenReturn(List.of(first, second));
        when(sourceResolver.latestSourceRefIds(projectId, revisionId, MigrationInputSourceType.DEPENDENCY_RESULT))
                .thenReturn(List.of(second.sourceRefId()));

        var result = service().list(projectId, revisionId,
                new MigrationInputListRequest(1, 1, MigrationInputSourceType.KB_FINDING, " high ",
                        MigrationInputStatus.CONFIRMED, " alpha ", "issueTitle", "asc"), actorId, false);

        assertThat(result.total()).isEqualTo(1);
        assertThat(result.items()).singleElement().extracting(MigrationInputResponse::issueTitle).isEqualTo("Alpha issue");
    }

    @Test
    void listSupportsEverySortFieldAndRejectsUnknownSort() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        MigrationInputRefView first = ref(projectId, revisionId, UUID.randomUUID(), "Zulu", MigrationInputStatus.CONFIRMED);
        MigrationInputRefView second = ref(projectId, revisionId, UUID.randomUUID(), "Alpha", MigrationInputStatus.CANDIDATE);
        when(migrationInputRepository.listAll(projectId, revisionId)).thenReturn(List.of(first, second));
        for (String sortBy : List.of("createdAt", "updatedAt", "sourceType", "detectedLevel", "status", "issueTitle", "")) {
            assertThat(service().list(projectId, revisionId,
                    new MigrationInputListRequest(null, null, null, null, null, null, sortBy, "desc"), actorId, false)
                    .items()).hasSize(2);
        }
        assertThatThrownBy(() -> service().list(projectId, revisionId,
                new MigrationInputListRequest(null, null, null, null, null, null, "bad", "asc"), actorId, false))
                .isInstanceOf(ApiException.class).extracting("code").isEqualTo("MIGRATION_INPUT_QUERY_INVALID");
    }

    @Test
    void deprecatedAutoMergeProcessesDefaultsNoResultsAndCreatedItems() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        UUID setId = UUID.randomUUID();
        UUID dependencyId = UUID.randomUUID();
        when(projectAccessService.requireSourceRevisionAccess(projectId, revisionId, actorId, false))
                .thenReturn(revision(projectId, revisionId));
        when(migrationInputRepository.ensureActiveSet(projectId, revisionId)).thenReturn(setId);
        when(sourceResolver.latestSourceRefIds(projectId, revisionId, MigrationInputSourceType.KB_FINDING))
                .thenReturn(List.of());
        when(sourceResolver.latestSourceRefIds(projectId, revisionId, MigrationInputSourceType.DEPENDENCY_RESULT))
                .thenReturn(List.of(dependencyId));
        MigrationInputCandidate candidate = candidate(projectId, revisionId, dependencyId, "dependency",
                MigrationInputSourceType.DEPENDENCY_RESULT);
        when(sourceResolver.resolve(projectId, revisionId, MigrationInputSourceType.DEPENDENCY_RESULT, dependencyId))
                .thenReturn(candidate);
        when(migrationInputRepository.insertCandidates(setId, List.of(candidate)))
                .thenReturn(new MigrationInputRepository.InsertResult(List.of(
                        dependencyRef(projectId, revisionId, dependencyId, "dependency", MigrationInputStatus.CONFIRMED,
                                "HIGH/MISSING", "BUILD_TOOL", "gcc")), 2));

        MigrationInputAutoMergeResponse result = service().autoMergeDeprecated(projectId, revisionId, null, actorId, false);

        assertThat(result.created()).isEqualTo(1);
        assertThat(result.skipped()).isEqualTo(2);
        assertThat(result.noResult()).isEqualTo(1);
        assertThat(result.sources()).hasSize(2);
    }

    @Test
    void deprecatedAutoMergeDeduplicatesSourceTypes() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        UUID actorId = UUID.randomUUID();
        when(projectAccessService.requireSourceRevisionAccess(projectId, revisionId, actorId, false))
                .thenReturn(revision(projectId, revisionId));
        when(migrationInputRepository.ensureActiveSet(projectId, revisionId)).thenReturn(UUID.randomUUID());
        when(sourceResolver.latestSourceRefIds(projectId, revisionId, MigrationInputSourceType.KB_FINDING))
                .thenReturn(List.of());

        MigrationInputAutoMergeResponse result = service().autoMergeDeprecated(projectId, revisionId,
                new MigrationInputAutoMergeRequest(List.of(MigrationInputSourceType.KB_FINDING, MigrationInputSourceType.KB_FINDING)), actorId, false);

        assertThat(result.sources()).singleElement().extracting(MigrationInputAutoMergeResponse.SourceResult::sourceType)
                .isEqualTo(MigrationInputSourceType.KB_FINDING);
    }

    @Test
    void detailReturnsSourceInformationAndRejectsMissingReference() {
        UUID actorId = UUID.randomUUID();
        MigrationInputRefView ref = ref(UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), "issue", MigrationInputStatus.CONFIRMED);
        when(migrationInputRepository.findById(ref.id())).thenReturn(java.util.Optional.of(ref));
        when(sourceResolver.detail(ref)).thenReturn(java.util.Map.of("code", "line"));

        assertThat(service().detail(ref.id(), actorId, false).sourceDetail()).containsEntry("code", "line");

        UUID missing = UUID.randomUUID();
        when(migrationInputRepository.findById(missing)).thenReturn(java.util.Optional.empty());
        assertThatThrownBy(() -> service().detail(missing, actorId, false))
                .isInstanceOf(ApiException.class).extracting("code").isEqualTo("MIGRATION_INPUT_NOT_FOUND");
    }

    @Test
    void updateRequiresChangesAndReturnsUpdatedReference() {
        UUID actorId = UUID.randomUUID();
        MigrationInputRefView ref = ref(UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), "issue", MigrationInputStatus.CANDIDATE);
        when(migrationInputRepository.findById(ref.id())).thenReturn(java.util.Optional.of(ref));
        assertThatThrownBy(() -> service().update(ref.id(), new MigrationInputUpdateRequest(null, null), actorId, false))
                .isInstanceOf(ApiException.class).extracting("code").isEqualTo("MIGRATION_INPUT_UPDATE_EMPTY");

        MigrationInputRefView updated = ref(ref.projectId(), ref.sourceRevisionId(), ref.sourceRefId(), "issue", MigrationInputStatus.EXCLUDED);
        when(migrationInputRepository.update(ref.id(), MigrationInputStatus.EXCLUDED, "manual"))
                .thenReturn(updated);
        assertThat(service().update(ref.id(), new MigrationInputUpdateRequest(MigrationInputStatus.EXCLUDED, "manual"), actorId, false).status())
                .isEqualTo(MigrationInputStatus.EXCLUDED);

        when(migrationInputRepository.update(ref.id(), null, "note")).thenReturn(null);
        assertThatThrownBy(() -> service().update(ref.id(), new MigrationInputUpdateRequest(null, "note"), actorId, false))
                .isInstanceOf(ApiException.class).extracting("code").isEqualTo("MIGRATION_INPUT_NOT_FOUND");
    }

    @Test
    void currentRefsHandlesNullEmptyAndMissingLatestDependencyIds() {
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        when(migrationInputRepository.listAll(projectId, revisionId)).thenReturn(null, List.of());
        assertThat(service().currentRefsForSystem(projectId, revisionId)).isEmpty();
        assertThat(service().currentRefsForSystem(projectId, revisionId)).isEmpty();

        MigrationInputRefView dependency = dependencyRef(projectId, revisionId, UUID.randomUUID(), "gcc",
                MigrationInputStatus.CANDIDATE, "HIGH/MISSING", "BUILD_TOOL", "gcc");
        when(migrationInputRepository.listAll(projectId, revisionId)).thenReturn(List.of(dependency));
        when(sourceResolver.latestSourceRefIds(projectId, revisionId, MigrationInputSourceType.DEPENDENCY_RESULT))
                .thenReturn(null);
        assertThat(service().currentRefsForSystem(projectId, revisionId)).isEmpty();
    }

    @Test
    void preferenceRanksEveryStatusAndRiskLevel() {
        MigrationInputService service = service();
        for (MigrationInputStatus status : MigrationInputStatus.values()) {
            int rank = (int) ReflectionTestUtils.invokeMethod(service, "statusRank", status);
            assertThat(rank).isEqualTo(switch (status) {
                case EXCLUDED -> 0;
                case CONFIRMED -> 1;
                case CANDIDATE -> 2;
            });
        }
        assertThat((int) ReflectionTestUtils.invokeMethod(service, "statusRank", (MigrationInputStatus) null)).isEqualTo(3);

        List<String> levels = List.of("CRITICAL/MISSING", "HIGH/MISSING", "MEDIUM/REPO_AVAILABLE",
                "LOW/TARGET_NEWER", "INFO/TARGET_INSTALLED", "COMMENT", "unknown");
        assertThat(levels.stream()
                .map(level -> (Integer) ReflectionTestUtils.invokeMethod(service, "riskRank", level)))
                .containsExactly(0, 1, 2, 3, 4, 5, 4);
    }

    @Test
    void preferenceUsesStatusThenRiskThenUpdatedAndCreatedTimes() {
        MigrationInputService service = service();
        UUID projectId = UUID.randomUUID();
        UUID revisionId = UUID.randomUUID();
        OffsetDateTime old = OffsetDateTime.now().minusDays(1);
        OffsetDateTime recent = OffsetDateTime.now();
        MigrationInputRefView candidate = dependencyRefAt(projectId, revisionId, MigrationInputStatus.CANDIDATE,
                "CRITICAL/MISSING", old, old);
        MigrationInputRefView confirmed = dependencyRefAt(projectId, revisionId, MigrationInputStatus.CONFIRMED,
                "LOW/TARGET_NEWER", old, old);
        MigrationInputRefView high = dependencyRefAt(projectId, revisionId, MigrationInputStatus.CONFIRMED,
                "HIGH/MISSING", old, old);
        MigrationInputRefView newerUpdated = dependencyRefAt(projectId, revisionId, MigrationInputStatus.CONFIRMED,
                "HIGH/MISSING", old, recent);
        MigrationInputRefView newerCreated = dependencyRefAt(projectId, revisionId, MigrationInputStatus.CONFIRMED,
                "HIGH/MISSING", recent, null);
        MigrationInputRefView olderCreated = dependencyRefAt(projectId, revisionId, MigrationInputStatus.CONFIRMED,
                "HIGH/MISSING", old, null);
        MigrationInputRefView noTimes = dependencyRefAt(projectId, revisionId, MigrationInputStatus.CONFIRMED,
                "HIGH/MISSING", null, null);

        assertThat((boolean) ReflectionTestUtils.invokeMethod(service, "prefer", confirmed, candidate)).isTrue();
        assertThat((boolean) ReflectionTestUtils.invokeMethod(service, "prefer", candidate, confirmed)).isFalse();
        assertThat((boolean) ReflectionTestUtils.invokeMethod(service, "prefer", high, confirmed)).isTrue();
        assertThat((boolean) ReflectionTestUtils.invokeMethod(service, "prefer", confirmed, high)).isFalse();
        assertThat((boolean) ReflectionTestUtils.invokeMethod(service, "prefer", newerUpdated, high)).isTrue();
        assertThat((boolean) ReflectionTestUtils.invokeMethod(service, "prefer", high, newerUpdated)).isFalse();
        assertThat((boolean) ReflectionTestUtils.invokeMethod(service, "prefer", newerCreated, olderCreated)).isTrue();
        assertThat((boolean) ReflectionTestUtils.invokeMethod(service, "prefer", olderCreated, newerCreated)).isFalse();
        assertThat((boolean) ReflectionTestUtils.invokeMethod(service, "prefer", noTimes, high)).isFalse();
    }

    @Test
    void keywordMatchingCoversTitleLocationRecommendationAndNullValues() {
        MigrationInputService service = service();
        MigrationInputRefView ref = ref(UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(),
                "Alpha issue", MigrationInputStatus.CONFIRMED);

        assertThat((boolean) ReflectionTestUtils.invokeMethod(service, "matchesKeyword", ref, null)).isTrue();
        assertThat((boolean) ReflectionTestUtils.invokeMethod(service, "matchesKeyword", ref, "  ")).isTrue();
        assertThat((boolean) ReflectionTestUtils.invokeMethod(service, "matchesKeyword", ref, "ALPHA")).isTrue();
        assertThat((boolean) ReflectionTestUtils.invokeMethod(service, "matchesKeyword", ref, "SRC/A.C")).isTrue();
        assertThat((boolean) ReflectionTestUtils.invokeMethod(service, "matchesKeyword", ref, "FIX")).isTrue();
        assertThat((boolean) ReflectionTestUtils.invokeMethod(service, "matchesKeyword", ref, "absent")).isFalse();
        assertThat((boolean) ReflectionTestUtils.invokeMethod(service, "contains", null, "x")).isFalse();
    }

    private MigrationInputService service() {
        return new MigrationInputService(migrationInputRepository, sourceResolver, projectAccessService);
    }

    private SourceRevisionView revision(UUID projectId, UUID sourceRevisionId) {
        return new SourceRevisionView(
                sourceRevisionId,
                projectId,
                SourceRevisionType.GIT,
                "main",
                "https://example.test/repo.git",
                "https://example.test/repo.git",
                "main",
                "abc",
                null,
                "/tmp/source",
                null,
                true,
                UUID.randomUUID(),
                OffsetDateTime.now()
        );
    }

    private MigrationInputCandidate candidate(UUID projectId, UUID sourceRevisionId, UUID refId, String title) {
        return candidate(projectId, sourceRevisionId, refId, title, MigrationInputSourceType.KB_FINDING);
    }

    private MigrationInputCandidate candidate(UUID projectId, UUID sourceRevisionId, UUID refId, String title, MigrationInputSourceType sourceType) {
        return candidate(projectId, sourceRevisionId, refId, title, sourceType, "HIGH");
    }

    private MigrationInputCandidate candidate(UUID projectId, UUID sourceRevisionId, UUID refId, String title, MigrationInputSourceType sourceType, String detectedLevel) {
        return new MigrationInputCandidate(projectId, sourceRevisionId, title, sourceType, refId,
                detectedLevel, "src/a.c:1", "fix", "rule", "src/a.c", "func", "anchor", "fingerprint", MigrationInputStatus.CONFIRMED);
    }

    private MigrationInputRefView ref(UUID projectId, UUID sourceRevisionId, UUID sourceRefId, String title, MigrationInputStatus status) {
        return new MigrationInputRefView(
                UUID.randomUUID(),
                UUID.randomUUID(),
                projectId,
                sourceRevisionId,
                title,
                MigrationInputSourceType.KB_FINDING,
                sourceRefId,
                "high",
                "src/a.c:1",
                "fix",
                "rule",
                "src/a.c",
                "func",
                "anchor",
                "fingerprint",
                status,
                null,
                OffsetDateTime.now(),
                null
        );
    }

    private MigrationInputRefView dependencyRef(
            UUID projectId,
            UUID sourceRevisionId,
            UUID sourceRefId,
            String title,
            MigrationInputStatus status,
            String detectedLevel,
            String dependencyType,
            String dependencyName
    ) {
        return new MigrationInputRefView(
                UUID.randomUUID(),
                UUID.randomUUID(),
                projectId,
                sourceRevisionId,
                title,
                MigrationInputSourceType.DEPENDENCY_RESULT,
                sourceRefId,
                detectedLevel,
                dependencyType.toLowerCase() + ":" + dependencyName,
                "fix",
                dependencyType,
                dependencyName,
                dependencyName,
                "anchor",
                "fingerprint-" + dependencyName,
                status,
                null,
                OffsetDateTime.now(),
                OffsetDateTime.now()
        );
    }

    private MigrationInputRefView dependencyRefAt(
            UUID projectId,
            UUID sourceRevisionId,
            MigrationInputStatus status,
            String detectedLevel,
            OffsetDateTime createdAt,
            OffsetDateTime updatedAt
    ) {
        return new MigrationInputRefView(
                UUID.randomUUID(), UUID.randomUUID(), projectId, sourceRevisionId, "gcc dependency",
                MigrationInputSourceType.DEPENDENCY_RESULT, UUID.randomUUID(), detectedLevel,
                "build_tool:gcc", "fix", "BUILD_TOOL", "gcc", "gcc", "anchor", "fingerprint",
                status, null, createdAt, updatedAt
        );
    }
}
