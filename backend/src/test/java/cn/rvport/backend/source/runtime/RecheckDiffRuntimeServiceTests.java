package cn.rvport.backend.source.runtime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import cn.rvport.backend.archive.ArchiveCandidateRegistrar;
import cn.rvport.backend.migration.MigrationInputRefView;
import cn.rvport.backend.migration.MigrationInputRepository;
import cn.rvport.backend.migration.MigrationInputSourceResolver;
import cn.rvport.backend.migration.MigrationInputSourceType;
import cn.rvport.backend.migration.MigrationInputStatus;
import cn.rvport.backend.source.RecheckTaskInput;
import cn.rvport.backend.source.SourceCompareRepository;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.worker.TaskExecutionContext;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class RecheckDiffRuntimeServiceTests {

    @Mock
    private MigrationInputRepository migrationInputRepository;

    @Mock
    private MigrationInputSourceResolver sourceResolver;

    @Mock
    private SourceCompareRepository sourceCompareRepository;

    @Mock
    private ArchiveCandidateRegistrar archiveCandidateRegistrar;

    @Mock
    private TaskExecutionContext context;

    @org.junit.jupiter.api.BeforeEach
    void allowPublication() {
        org.mockito.Mockito.lenient().when(context.publish(any()))
                .thenAnswer(call -> ((java.util.function.Supplier<?>) call.getArgument(0)).get());
    }

    @Test
    void lostAttemptDoesNotOverwriteRecheckStatus() {
        doThrow(new cn.rvport.backend.worker.TaskAttemptLostException()).when(context).publish(any());
        org.assertj.core.api.Assertions.assertThatThrownBy(() -> service().run(new RecheckTaskInput(
                UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID()), context))
                .isInstanceOf(cn.rvport.backend.worker.TaskAttemptLostException.class);
        org.mockito.Mockito.verifyNoInteractions(sourceCompareRepository, migrationInputRepository, archiveCandidateRegistrar);
    }

    @Test
    void generatesAllDiffStatusesFromConfirmedMigrationInputs() {
        UUID projectId = UUID.randomUUID();
        UUID baseRevisionId = UUID.randomUUID();
        UUID targetRevisionId = UUID.randomUUID();
        UUID recheckRunId = UUID.randomUUID();
        MigrationInputRefView unchangedOld = ref(projectId, baseRevisionId, "same", "same-fp", "src/a.c:10", "high", "fix");
        MigrationInputRefView unchangedNew = ref(projectId, targetRevisionId, "same", "same-fp", "src/a.c:30", "high", "fix");
        MigrationInputRefView changedOld = ref(projectId, baseRevisionId, "changed", "changed-fp-old", "src/b.c:10", "medium", "old fix");
        MigrationInputRefView changedNew = ref(projectId, targetRevisionId, "changed", "changed-fp-new", "src/b.c:20", "high", "new fix");
        MigrationInputRefView resolved = ref(projectId, baseRevisionId, "resolved", "resolved-fp", "src/c.c:1", "high", "fix");
        MigrationInputRefView added = ref(projectId, targetRevisionId, "added", "added-fp", "src/d.c:1", "low", "fix");
        when(migrationInputRepository.confirmedRefs(projectId, baseRevisionId)).thenReturn(List.of(unchangedOld, changedOld, resolved));
        when(migrationInputRepository.confirmedRefs(projectId, targetRevisionId)).thenReturn(List.of(unchangedNew, changedNew, added));
        for (MigrationInputRefView ref : List.of(unchangedOld, unchangedNew, changedOld, changedNew, resolved, added)) {
            when(sourceResolver.detail(ref)).thenReturn(Map.of("ruleId", ref.ruleId(), "filePath", ref.identityPath(), "symbol", ref.identitySymbol(), "fingerprint", ref.identityAnchor()));
        }

        service().run(new RecheckTaskInput(projectId, recheckRunId, baseRevisionId, targetRevisionId), context);

        ArgumentCaptor<List<SourceCompareRepository.DiffItemCreateCommand>> captor = ArgumentCaptor.captor();
        verify(sourceCompareRepository).replaceDiffItems(eq(projectId), eq(recheckRunId), captor.capture());
        assertThat(captor.getValue()).extracting(SourceCompareRepository.DiffItemCreateCommand::diffStatus)
                .containsExactlyInAnyOrder("UNCHANGED", "CHANGED", "RESOLVED", "NEW");
        assertThat(captor.getValue())
                .filteredOn(item -> item.diffStatus().equals("UNCHANGED"))
                .singleElement()
                .satisfies(item -> {
                    assertThat(item.matchConfidence()).isEqualTo("HIGH");
                    assertThat(item.matchReason()).isEqualTo("EXACT_FINGERPRINT");
                });
        assertThat(captor.getValue())
                .filteredOn(item -> item.diffStatus().equals("CHANGED"))
                .singleElement()
                .satisfies(item -> {
                    assertThat(item.matchConfidence()).isEqualTo("HIGH");
                    assertThat(item.matchReason()).isEqualTo("SAME_RULE_PATH_SYMBOL_ANCHOR");
                });
        verify(sourceCompareRepository).updateRecheckStatus(eq(recheckRunId), eq(TaskStatus.SUCCEEDED), any());
    }

    @Test
    void marksRecheckFailedWhenDiffGenerationFails() {
        UUID projectId = UUID.randomUUID();
        UUID baseRevisionId = UUID.randomUUID();
        UUID targetRevisionId = UUID.randomUUID();
        UUID recheckRunId = UUID.randomUUID();
        when(migrationInputRepository.confirmedRefs(projectId, baseRevisionId)).thenThrow(new IllegalStateException("boom"));

        org.assertj.core.api.Assertions.assertThatThrownBy(() ->
                        service().run(new RecheckTaskInput(projectId, recheckRunId, baseRevisionId, targetRevisionId), context))
                .isInstanceOf(cn.rvport.backend.task.TaskExecutionException.class);

        verify(sourceCompareRepository).updateRecheckStatus(eq(recheckRunId), eq(TaskStatus.FAILED), any());
    }

    @Test
    void keepsRunningWhenSourceDetailIsMissing() {
        UUID projectId = UUID.randomUUID();
        UUID baseRevisionId = UUID.randomUUID();
        UUID targetRevisionId = UUID.randomUUID();
        UUID recheckRunId = UUID.randomUUID();
        MigrationInputRefView oldItem = ref(projectId, baseRevisionId, "detail missing", "missing-fp", "src/missing.c:1", "high", "fix");
        MigrationInputRefView newItem = ref(projectId, targetRevisionId, "detail missing", "missing-fp", "src/missing.c:3", "high", "fix");
        when(migrationInputRepository.confirmedRefs(projectId, baseRevisionId)).thenReturn(List.of(oldItem));
        when(migrationInputRepository.confirmedRefs(projectId, targetRevisionId)).thenReturn(List.of(newItem));
        doThrow(new IllegalStateException("source detail gone")).when(sourceResolver).detail(oldItem);
        doThrow(new IllegalStateException("source detail gone")).when(sourceResolver).detail(newItem);

        service().run(new RecheckTaskInput(projectId, recheckRunId, baseRevisionId, targetRevisionId), context);

        ArgumentCaptor<List<SourceCompareRepository.DiffItemCreateCommand>> captor = ArgumentCaptor.captor();
        verify(sourceCompareRepository).replaceDiffItems(eq(projectId), eq(recheckRunId), captor.capture());
        assertThat(captor.getValue()).singleElement().satisfies(item -> {
            assertThat(item.diffStatus()).isEqualTo("UNCHANGED");
            assertThat(item.oldSnapshot()).containsKey("detail");
            Map<?, ?> detail = (Map<?, ?>) item.oldSnapshot().get("detail");
            assertThat(detail.get("detailError")).isEqualTo("source detail gone");
        });
        verify(sourceCompareRepository).updateRecheckStatus(eq(recheckRunId), eq(TaskStatus.SUCCEEDED), any());
    }

    @Test
    void usesLowConfidenceWhenOnlyRuleAndAnchorMatch() {
        UUID projectId = UUID.randomUUID();
        UUID baseRevisionId = UUID.randomUUID();
        UUID targetRevisionId = UUID.randomUUID();
        UUID recheckRunId = UUID.randomUUID();
        MigrationInputRefView oldItem = ref(projectId, baseRevisionId, "moved issue", "old-fp", "src/old.c:1", "high", "fix", "RULE.MOVED", "src/old.c", "oldSymbol", "anchor");
        MigrationInputRefView newItem = ref(projectId, targetRevisionId, "moved issue", "new-fp", "src/new.c:9", "high", "fix", "RULE.MOVED", "src/new.c", "newSymbol", "anchor");
        when(migrationInputRepository.confirmedRefs(projectId, baseRevisionId)).thenReturn(List.of(oldItem));
        when(migrationInputRepository.confirmedRefs(projectId, targetRevisionId)).thenReturn(List.of(newItem));
        when(sourceResolver.detail(oldItem)).thenReturn(Map.of("ruleId", oldItem.ruleId(), "filePath", oldItem.identityPath(), "symbol", oldItem.identitySymbol(), "fingerprint", oldItem.identityAnchor()));
        when(sourceResolver.detail(newItem)).thenReturn(Map.of("ruleId", newItem.ruleId(), "filePath", newItem.identityPath(), "symbol", newItem.identitySymbol(), "fingerprint", newItem.identityAnchor()));

        service().run(new RecheckTaskInput(projectId, recheckRunId, baseRevisionId, targetRevisionId), context);

        ArgumentCaptor<List<SourceCompareRepository.DiffItemCreateCommand>> captor = ArgumentCaptor.captor();
        verify(sourceCompareRepository).replaceDiffItems(eq(projectId), eq(recheckRunId), captor.capture());
        assertThat(captor.getValue()).singleElement().satisfies(item -> {
            assertThat(item.diffStatus()).isEqualTo("CHANGED");
            assertThat(item.matchConfidence()).isEqualTo("LOW");
            assertThat(item.matchReason()).isEqualTo("SAME_RULE_ANCHOR");
        });
    }

    @Test
    void usesMediumConfidenceWhenRulePathAndAnchorMatchButSymbolChanges() {
        UUID projectId = UUID.randomUUID();
        UUID baseRevisionId = UUID.randomUUID();
        UUID targetRevisionId = UUID.randomUUID();
        UUID recheckRunId = UUID.randomUUID();
        MigrationInputRefView oldItem = ref(projectId, baseRevisionId, "issue", "old-fp", "src/a.c:1",
                "high", "fix", "RULE", "src/a.c", "oldSymbol", "anchor");
        MigrationInputRefView newItem = ref(projectId, targetRevisionId, "issue", "new-fp", "src/a.c:9",
                "high", "fix", "RULE", "src/a.c", "newSymbol", "anchor");
        when(migrationInputRepository.confirmedRefs(projectId, baseRevisionId)).thenReturn(List.of(oldItem));
        when(migrationInputRepository.confirmedRefs(projectId, targetRevisionId)).thenReturn(List.of(newItem));
        when(sourceResolver.detail(oldItem)).thenReturn(Map.of());
        when(sourceResolver.detail(newItem)).thenReturn(Map.of());

        service().run(new RecheckTaskInput(projectId, recheckRunId, baseRevisionId, targetRevisionId), context);

        ArgumentCaptor<List<SourceCompareRepository.DiffItemCreateCommand>> captor = ArgumentCaptor.captor();
        verify(sourceCompareRepository).replaceDiffItems(eq(projectId), eq(recheckRunId), captor.capture());
        assertThat(captor.getValue()).singleElement().satisfies(item -> {
            assertThat(item.matchConfidence()).isEqualTo("MEDIUM");
            assertThat(item.matchReason()).isEqualTo("SAME_RULE_PATH_ANCHOR");
        });
    }

    @Test
    void doesNotReuseOneTargetForDuplicateBaseFingerprint() {
        UUID projectId = UUID.randomUUID();
        UUID baseRevisionId = UUID.randomUUID();
        UUID targetRevisionId = UUID.randomUUID();
        UUID recheckRunId = UUID.randomUUID();
        MigrationInputRefView oldOne = ref(projectId, baseRevisionId, "same", "duplicate", "src/a.c:1", "high", "fix");
        MigrationInputRefView oldTwo = ref(projectId, baseRevisionId, "same", "duplicate", "src/a.c:1", "high", "fix");
        MigrationInputRefView target = ref(projectId, targetRevisionId, "same", "duplicate", "src/a.c:1", "high", "fix");
        when(migrationInputRepository.confirmedRefs(projectId, baseRevisionId)).thenReturn(List.of(oldOne, oldTwo));
        when(migrationInputRepository.confirmedRefs(projectId, targetRevisionId)).thenReturn(List.of(target));
        when(sourceResolver.detail(any())).thenReturn(Map.of());

        service().run(new RecheckTaskInput(projectId, recheckRunId, baseRevisionId, targetRevisionId), context);

        ArgumentCaptor<List<SourceCompareRepository.DiffItemCreateCommand>> captor = ArgumentCaptor.captor();
        verify(sourceCompareRepository).replaceDiffItems(eq(projectId), eq(recheckRunId), captor.capture());
        assertThat(captor.getValue()).extracting(SourceCompareRepository.DiffItemCreateCommand::diffStatus)
                .containsExactly("UNCHANGED", "RESOLVED");
    }

    @Test
    void computesFingerprintFromDetailFallbacksAndNormalizesWindowsPath() {
        UUID projectId = UUID.randomUUID();
        UUID baseRevisionId = UUID.randomUUID();
        UUID targetRevisionId = UUID.randomUUID();
        UUID recheckRunId = UUID.randomUUID();
        MigrationInputRefView oldItem = sparseRef(projectId, baseRevisionId);
        MigrationInputRefView newItem = sparseRef(projectId, targetRevisionId);
        when(migrationInputRepository.confirmedRefs(projectId, baseRevisionId)).thenReturn(List.of(oldItem));
        when(migrationInputRepository.confirmedRefs(projectId, targetRevisionId)).thenReturn(List.of(newItem));
        Map<String, Object> detail = new java.util.LinkedHashMap<>();
        detail.put("componentType", "LIBRARY");
        detail.put("filePath", "SRC\\LIB.C");
        detail.put("sourceName", "Symbol");
        detail.put("title", "Anchor");
        when(sourceResolver.detail(oldItem)).thenReturn(detail);
        when(sourceResolver.detail(newItem)).thenReturn(detail);

        service().run(new RecheckTaskInput(projectId, recheckRunId, baseRevisionId, targetRevisionId), context);

        ArgumentCaptor<List<SourceCompareRepository.DiffItemCreateCommand>> captor = ArgumentCaptor.captor();
        verify(sourceCompareRepository).replaceDiffItems(eq(projectId), eq(recheckRunId), captor.capture());
        assertThat(captor.getValue()).singleElement().satisfies(item -> {
            assertThat(item.diffStatus()).isEqualTo("UNCHANGED");
            assertThat(item.fingerprint()).hasSize(64);
            assertThat(item.newLocation()).containsEntry("identityPath", "src/lib.c");
        });
    }

    @Test
    void rethrowsTaskExecutionFailureAndUsesClassNameForBlankMessage() {
        UUID projectId = UUID.randomUUID();
        UUID runId = UUID.randomUUID();
        UUID base = UUID.randomUUID();
        cn.rvport.backend.task.TaskExecutionException failure = new cn.rvport.backend.task.TaskExecutionException(
                "INPUT_INVALID", "", null);
        when(migrationInputRepository.confirmedRefs(projectId, base)).thenThrow(failure);

        org.assertj.core.api.Assertions.assertThatThrownBy(() -> service().run(
                new RecheckTaskInput(projectId, runId, base, UUID.randomUUID()), context))
                .isSameAs(failure);

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, Object>> summary = ArgumentCaptor.forClass(Map.class);
        verify(sourceCompareRepository).updateRecheckStatus(eq(runId), eq(TaskStatus.FAILED), summary.capture());
        assertThat(summary.getValue()).containsEntry("message", "TaskExecutionException");
    }

    @Test
    void detectsChangesInRecommendationPathSymbolAndAnchorIndependently() {
        UUID projectId = UUID.randomUUID();
        UUID baseRevisionId = UUID.randomUUID();
        UUID targetRevisionId = UUID.randomUUID();
        UUID recheckRunId = UUID.randomUUID();
        List<MigrationInputRefView> oldItems = List.of(
                ref(projectId, baseRevisionId, "issue", "fp-1", "a", "high", "old", "RULE", "path", "symbol", "anchor"),
                ref(projectId, baseRevisionId, "issue", "fp-2", "a", "high", "fix", "RULE", "old-path", "symbol", "anchor"),
                ref(projectId, baseRevisionId, "issue", "fp-3", "a", "high", "fix", "RULE", "path", "old-symbol", "anchor"),
                ref(projectId, baseRevisionId, "issue", "fp-4", "a", "high", "fix", "RULE", "path", "symbol", "old-anchor"));
        List<MigrationInputRefView> newItems = List.of(
                ref(projectId, targetRevisionId, "issue", "fp-1", "a", "high", "new", "RULE", "path", "symbol", "anchor"),
                ref(projectId, targetRevisionId, "issue", "fp-2", "a", "high", "fix", "RULE", "new-path", "symbol", "anchor"),
                ref(projectId, targetRevisionId, "issue", "fp-3", "a", "high", "fix", "RULE", "path", "new-symbol", "anchor"),
                ref(projectId, targetRevisionId, "issue", "fp-4", "a", "high", "fix", "RULE", "path", "symbol", "new-anchor"));
        when(migrationInputRepository.confirmedRefs(projectId, baseRevisionId)).thenReturn(oldItems);
        when(migrationInputRepository.confirmedRefs(projectId, targetRevisionId)).thenReturn(newItems);
        when(sourceResolver.detail(any())).thenReturn(Map.of());

        service().run(new RecheckTaskInput(projectId, recheckRunId, baseRevisionId, targetRevisionId), context);

        ArgumentCaptor<List<SourceCompareRepository.DiffItemCreateCommand>> captor = ArgumentCaptor.captor();
        verify(sourceCompareRepository).replaceDiffItems(eq(projectId), eq(recheckRunId), captor.capture());
        assertThat(captor.getValue()).hasSize(4)
                .allSatisfy(item -> assertThat(item.diffStatus()).isEqualTo("CHANGED"));
    }

    @Test
    void sourceTypeMismatchCannotFuzzyMatchOtherwiseEquivalentItems() {
        UUID projectId = UUID.randomUUID();
        UUID baseRevisionId = UUID.randomUUID();
        UUID targetRevisionId = UUID.randomUUID();
        UUID recheckRunId = UUID.randomUUID();
        MigrationInputRefView oldItem = ref(projectId, baseRevisionId, "issue", "old", "src/a.c:1", "high", "fix");
        MigrationInputRefView newItem = new MigrationInputRefView(
                UUID.randomUUID(), UUID.randomUUID(), projectId, targetRevisionId, "issue",
                MigrationInputSourceType.DEPENDENCY_RESULT, UUID.randomUUID(), "high", "src/a.c:1", "fix",
                oldItem.ruleId(), oldItem.identityPath(), oldItem.identitySymbol(), oldItem.identityAnchor(), "new",
                MigrationInputStatus.CONFIRMED, null, OffsetDateTime.now(), null);
        when(migrationInputRepository.confirmedRefs(projectId, baseRevisionId)).thenReturn(List.of(oldItem));
        when(migrationInputRepository.confirmedRefs(projectId, targetRevisionId)).thenReturn(List.of(newItem));
        when(sourceResolver.detail(any())).thenReturn(Map.of());

        service().run(new RecheckTaskInput(projectId, recheckRunId, baseRevisionId, targetRevisionId), context);

        ArgumentCaptor<List<SourceCompareRepository.DiffItemCreateCommand>> captor = ArgumentCaptor.captor();
        verify(sourceCompareRepository).replaceDiffItems(eq(projectId), eq(recheckRunId), captor.capture());
        assertThat(captor.getValue()).extracting(SourceCompareRepository.DiffItemCreateCommand::diffStatus)
                .containsExactly("RESOLVED", "NEW");
    }

    private RecheckDiffRuntimeService service() {
        return new RecheckDiffRuntimeService(migrationInputRepository, sourceResolver, sourceCompareRepository, archiveCandidateRegistrar);
    }

    private MigrationInputRefView ref(
            UUID projectId,
            UUID sourceRevisionId,
            String title,
            String fingerprint,
            String location,
            String level,
            String recommendation
    ) {
        return new MigrationInputRefView(
                UUID.randomUUID(),
                UUID.randomUUID(),
                projectId,
                sourceRevisionId,
                title,
                MigrationInputSourceType.KB_FINDING,
                UUID.randomUUID(),
                level,
                location,
                recommendation,
                "rule",
                location.split(":")[0],
                "func",
                title,
                fingerprint,
                MigrationInputStatus.CONFIRMED,
                null,
                OffsetDateTime.now(),
                null
        );
    }

    private MigrationInputRefView sparseRef(UUID projectId, UUID sourceRevisionId) {
        return new MigrationInputRefView(
                UUID.randomUUID(), UUID.randomUUID(), projectId, sourceRevisionId, "issue",
                MigrationInputSourceType.KB_FINDING, UUID.randomUUID(), null, null, null,
                null, null, null, null, null, MigrationInputStatus.CONFIRMED,
                null, OffsetDateTime.now(), null);
    }

    private MigrationInputRefView ref(
            UUID projectId,
            UUID sourceRevisionId,
            String title,
            String fingerprint,
            String location,
            String level,
            String recommendation,
            String ruleId,
            String identityPath,
            String identitySymbol,
            String identityAnchor
    ) {
        return new MigrationInputRefView(
                UUID.randomUUID(),
                UUID.randomUUID(),
                projectId,
                sourceRevisionId,
                title,
                MigrationInputSourceType.KB_FINDING,
                UUID.randomUUID(),
                level,
                location,
                recommendation,
                ruleId,
                identityPath,
                identitySymbol,
                identityAnchor,
                fingerprint,
                MigrationInputStatus.CONFIRMED,
                null,
                OffsetDateTime.now(),
                null
        );
    }
}
