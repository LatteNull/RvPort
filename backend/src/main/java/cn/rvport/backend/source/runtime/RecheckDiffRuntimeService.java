package cn.rvport.backend.source.runtime;

import cn.rvport.backend.archive.ArchiveCandidateRegistrar;
import cn.rvport.backend.migration.MigrationInputRefView;
import cn.rvport.backend.migration.MigrationInputRepository;
import cn.rvport.backend.migration.MigrationInputSourceResolver;
import cn.rvport.backend.source.RecheckTaskInput;
import cn.rvport.backend.source.SourceCompareRepository;
import cn.rvport.backend.task.TaskExecutionException;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.worker.TaskExecutionContext;
import cn.rvport.backend.worker.TaskAttemptLostException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.function.Function;
import java.util.stream.Collectors;
import org.springframework.stereotype.Service;

@Service
public class RecheckDiffRuntimeService {

    private static final String ERROR_CODE = "RECHECK_DIFF_FAILED";

    private final MigrationInputRepository migrationInputRepository;
    private final MigrationInputSourceResolver sourceResolver;
    private final SourceCompareRepository sourceCompareRepository;
    private final ArchiveCandidateRegistrar archiveCandidateRegistrar;

    public RecheckDiffRuntimeService(
            MigrationInputRepository migrationInputRepository,
            MigrationInputSourceResolver sourceResolver,
            SourceCompareRepository sourceCompareRepository,
            ArchiveCandidateRegistrar archiveCandidateRegistrar
    ) {
        this.migrationInputRepository = migrationInputRepository;
        this.sourceResolver = sourceResolver;
        this.sourceCompareRepository = sourceCompareRepository;
        this.archiveCandidateRegistrar = archiveCandidateRegistrar;
    }

    public void run(RecheckTaskInput input, TaskExecutionContext context) {
        try {
            context.publish(() -> {
                sourceCompareRepository.updateRecheckStatus(input.recheckRunId(), TaskStatus.RUNNING, Map.of("phase", "matching"));
                return null;
            });
            context.progress(10, "正在读取已确认迁移输入");
            List<ComparableInput> base = migrationInputRepository.confirmedRefs(input.projectId(), input.baseSourceRevisionId())
                    .stream()
                    .map(this::comparableInput)
                    .toList();
            List<ComparableInput> target = migrationInputRepository.confirmedRefs(input.projectId(), input.targetSourceRevisionId())
                    .stream()
                    .map(this::comparableInput)
                    .toList();
            context.progress(35, "正在匹配迁移输入差异");
            List<SourceCompareRepository.DiffItemCreateCommand> diffItems = diff(input.projectId(), base, target);
            Map<String, Object> summary = summary(base.size(), target.size(), diffItems);
            context.progress(80, "正在写入复检差异结果");
            context.publish(() -> {
            sourceCompareRepository.replaceDiffItems(input.projectId(), input.recheckRunId(), diffItems);
            sourceCompareRepository.updateRecheckStatus(input.recheckRunId(), TaskStatus.SUCCEEDED, summary);
            sourceCompareRepository.findRecheckRun(input.recheckRunId())
                    .ifPresent(run -> archiveCandidateRegistrar.registerRecheck(run, summary));
            return null;
            });
            context.progress(100, "复检差异生成完成");
        } catch (TaskAttemptLostException ex) {
            throw ex;
        } catch (RuntimeException ex) {
            context.publish(() -> {
            sourceCompareRepository.updateRecheckStatus(input.recheckRunId(), TaskStatus.FAILED, Map.of(
                    "error", ERROR_CODE,
                    "message", safeMessage(ex)
            ));
            return null;
            });
            if (ex instanceof TaskExecutionException taskExecutionException) {
                throw taskExecutionException;
            }
            throw new TaskExecutionException(ERROR_CODE, safeMessage(ex), ex);
        }
    }

    private ComparableInput comparableInput(MigrationInputRefView ref) {
        Map<String, Object> detail;
        try {
            detail = sourceResolver.detail(ref);
        } catch (RuntimeException ex) {
            detail = Map.of("detailError", safeMessage(ex));
        }
        String ruleId = firstNonBlank(ref.ruleId(), string(detail.get("ruleId")), string(detail.get("componentType")), ref.sourceType().name());
        String path = firstNonBlank(ref.identityPath(), string(detail.get("filePath")), ref.locationLabel(), string(detail.get("sourcePackageName")), string(detail.get("sourceName")));
        String symbol = firstNonBlank(ref.identitySymbol(), string(detail.get("symbol")), string(detail.get("sourcePackageName")), string(detail.get("sourceName")));
        String anchor = firstNonBlank(ref.identityAnchor(), string(detail.get("fingerprint")), string(detail.get("title")), ref.issueTitle());
        String fingerprint = firstNonBlank(ref.stableFingerprint(), stableFingerprint(ref.sourceType().name(), ruleId, normalizePath(path), normalize(symbol), normalize(anchor)));
        Map<String, Object> snapshot = new LinkedHashMap<>();
        snapshot.put("id", ref.id());
        snapshot.put("projectId", ref.projectId());
        snapshot.put("sourceRevisionId", ref.sourceRevisionId());
        snapshot.put("issueTitle", ref.issueTitle());
        snapshot.put("sourceType", ref.sourceType().name());
        snapshot.put("sourceRefId", ref.sourceRefId());
        snapshot.put("detectedLevel", ref.detectedLevel());
        snapshot.put("locationLabel", ref.locationLabel());
        snapshot.put("recommendationSummary", ref.recommendationSummary());
        snapshot.put("confirmationStatus", ref.status().name());
        snapshot.put("ruleId", ruleId);
        snapshot.put("identityPath", path);
        snapshot.put("identitySymbol", symbol);
        snapshot.put("identityAnchor", anchor);
        snapshot.put("stableFingerprint", fingerprint);
        snapshot.put("detail", detail);
        return new ComparableInput(ref, detail, snapshot, ruleId, normalizePath(path), normalize(symbol), normalize(anchor), fingerprint);
    }

    private List<SourceCompareRepository.DiffItemCreateCommand> diff(UUID projectId, List<ComparableInput> base, List<ComparableInput> target) {
        List<SourceCompareRepository.DiffItemCreateCommand> result = new ArrayList<>();
        Map<String, ComparableInput> targetByFingerprint = target.stream()
                .filter(item -> !item.fingerprint().isBlank())
                .collect(Collectors.toMap(ComparableInput::fingerprint, Function.identity(), (left, right) -> left, LinkedHashMap::new));
        Set<UUID> matchedTargetIds = new HashSet<>();
        for (ComparableInput oldItem : base) {
            ComparableInput newItem = targetByFingerprint.get(oldItem.fingerprint());
            Match match = null;
            if (newItem != null && !matchedTargetIds.contains(newItem.ref().id())) {
                match = new Match(newItem, "HIGH", "EXACT_FINGERPRINT");
            } else {
                match = fuzzyMatch(oldItem, target, matchedTargetIds);
            }
            if (match == null) {
                result.add(command(projectId, "RESOLVED", oldItem, null, null, "UNMATCHED_OLD"));
            } else {
                matchedTargetIds.add(match.item().ref().id());
                result.add(command(projectId, changed(oldItem, match.item()) ? "CHANGED" : "UNCHANGED", oldItem, match.item(), match.confidence(), match.reason()));
            }
        }
        for (ComparableInput newItem : target) {
            if (!matchedTargetIds.contains(newItem.ref().id())) {
                result.add(command(projectId, "NEW", null, newItem, null, "UNMATCHED_NEW"));
            }
        }
        return result;
    }

    private Match fuzzyMatch(ComparableInput oldItem, List<ComparableInput> target, Set<UUID> matchedTargetIds) {
        for (ComparableInput candidate : target) {
            if (matchedTargetIds.contains(candidate.ref().id()) || oldItem.ref().sourceType() != candidate.ref().sourceType()) {
                continue;
            }
            if (same(oldItem.ruleId(), candidate.ruleId())
                    && same(oldItem.path(), candidate.path())
                    && same(oldItem.symbol(), candidate.symbol())
                    && same(oldItem.anchor(), candidate.anchor())) {
                return new Match(candidate, "HIGH", "SAME_RULE_PATH_SYMBOL_ANCHOR");
            }
        }
        for (ComparableInput candidate : target) {
            if (matchedTargetIds.contains(candidate.ref().id()) || oldItem.ref().sourceType() != candidate.ref().sourceType()) {
                continue;
            }
            if (same(oldItem.ruleId(), candidate.ruleId())
                    && same(oldItem.path(), candidate.path())
                    && same(oldItem.anchor(), candidate.anchor())) {
                return new Match(candidate, "MEDIUM", "SAME_RULE_PATH_ANCHOR");
            }
        }
        for (ComparableInput candidate : target) {
            if (matchedTargetIds.contains(candidate.ref().id()) || oldItem.ref().sourceType() != candidate.ref().sourceType()) {
                continue;
            }
            if (same(oldItem.ruleId(), candidate.ruleId()) && same(oldItem.anchor(), candidate.anchor())) {
                return new Match(candidate, "LOW", "SAME_RULE_ANCHOR");
            }
        }
        return null;
    }

    private SourceCompareRepository.DiffItemCreateCommand command(
            UUID projectId,
            String diffStatus,
            ComparableInput oldItem,
            ComparableInput newItem,
            String matchConfidence,
            String matchReason
    ) {
        ComparableInput display = newItem == null ? oldItem : newItem;
        return new SourceCompareRepository.DiffItemCreateCommand(
                display.ref().sourceType().name(),
                oldItem == null ? null : oldItem.ref().sourceRefId(),
                newItem == null ? null : newItem.ref().sourceRefId(),
                diffStatus,
                oldItem == null ? null : location(oldItem),
                newItem == null ? null : location(newItem),
                display.ref().detectedLevel(),
                display.ref().issueTitle(),
                display.ref().locationLabel(),
                display.ref().recommendationSummary(),
                display.ref().status().name(),
                firstNonBlank(display.fingerprint(), oldItem == null ? null : oldItem.fingerprint(), newItem == null ? null : newItem.fingerprint()),
                matchConfidence,
                matchReason,
                oldItem == null ? null : oldItem.snapshot(),
                newItem == null ? null : newItem.snapshot()
        );
    }

    private Map<String, Object> location(ComparableInput item) {
        Map<String, Object> value = new LinkedHashMap<>();
        value.put("label", item.ref().locationLabel());
        value.put("identityPath", item.path());
        return value;
    }

    private boolean changed(ComparableInput oldItem, ComparableInput newItem) {
        return !Objects.equals(oldItem.ref().issueTitle(), newItem.ref().issueTitle())
                || !Objects.equals(oldItem.ref().detectedLevel(), newItem.ref().detectedLevel())
                || !Objects.equals(oldItem.ref().recommendationSummary(), newItem.ref().recommendationSummary())
                || !Objects.equals(oldItem.path(), newItem.path())
                || !Objects.equals(oldItem.symbol(), newItem.symbol())
                || !Objects.equals(oldItem.anchor(), newItem.anchor());
    }

    private Map<String, Object> summary(int baseCount, int targetCount, List<SourceCompareRepository.DiffItemCreateCommand> items) {
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("baseConfirmedCount", baseCount);
        summary.put("targetConfirmedCount", targetCount);
        summary.put("total", items.size());
        summary.put("byStatus", grouped(items, SourceCompareRepository.DiffItemCreateCommand::diffStatus));
        summary.put("bySourceType", grouped(items, SourceCompareRepository.DiffItemCreateCommand::sourceType));
        summary.put("bySeverity", grouped(items, SourceCompareRepository.DiffItemCreateCommand::severity));
        summary.put("byMatchConfidence", grouped(items, item -> item.matchConfidence() == null ? "UNMATCHED" : item.matchConfidence()));
        return summary;
    }

    private Map<String, Long> grouped(List<SourceCompareRepository.DiffItemCreateCommand> items, Function<SourceCompareRepository.DiffItemCreateCommand, String> classifier) {
        Map<String, Long> grouped = new LinkedHashMap<>();
        items.stream()
                .collect(Collectors.groupingBy(item -> firstNonBlank(classifier.apply(item), "UNKNOWN"), LinkedHashMap::new, Collectors.counting()))
                .forEach(grouped::put);
        return grouped;
    }

    private boolean same(String left, String right) {
        return !left.isBlank() && Objects.equals(left, right);
    }

    private String stableFingerprint(String... parts) {
        String joined = String.join("|", parts);
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return HexFormat.of().formatHex(digest.digest(joined.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 is not available", ex);
        }
    }

    private String normalizePath(String value) {
        return normalize(value).replace('\\', '/');
    }

    private String normalize(String value) {
        return value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
    }

    private String firstNonBlank(String... values) {
        for (String value : values) {
            if (value != null && !value.isBlank()) {
                return value.trim();
            }
        }
        return "";
    }

    private String string(Object value) {
        return value == null ? null : String.valueOf(value);
    }

    private String safeMessage(Throwable ex) {
        return ex.getMessage() == null || ex.getMessage().isBlank() ? ex.getClass().getSimpleName() : ex.getMessage();
    }

    private record ComparableInput(
            MigrationInputRefView ref,
            Map<String, Object> detail,
            Map<String, Object> snapshot,
            String ruleId,
            String path,
            String symbol,
            String anchor,
            String fingerprint
    ) {
    }

    private record Match(ComparableInput item, String confidence, String reason) {
    }
}
