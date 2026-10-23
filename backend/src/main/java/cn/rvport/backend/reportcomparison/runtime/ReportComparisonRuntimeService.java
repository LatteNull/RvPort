package cn.rvport.backend.reportcomparison.runtime;

import cn.rvport.backend.archive.ArchiveCandidateRegistrar;
import cn.rvport.backend.report.ReportInputView;
import cn.rvport.backend.report.ReportRepository;
import cn.rvport.backend.report.ReportView;
import cn.rvport.backend.reportcomparison.ReportComparisonRepository;
import cn.rvport.backend.reportcomparison.ReportComparisonRunView;
import cn.rvport.backend.reportcomparison.ReportComparisonTaskInput;
import cn.rvport.backend.task.TaskErrorCode;
import cn.rvport.backend.task.TaskExecutionException;
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
public class ReportComparisonRuntimeService {

    private static final String ERROR_CODE = "REPORT_COMPARISON_FAILED";

    private final ReportRepository reportRepository;
    private final ReportComparisonRepository comparisonRepository;
    private final ArchiveCandidateRegistrar archiveCandidateRegistrar;

    public ReportComparisonRuntimeService(
            ReportRepository reportRepository,
            ReportComparisonRepository comparisonRepository,
            ArchiveCandidateRegistrar archiveCandidateRegistrar
    ) {
        this.reportRepository = reportRepository;
        this.comparisonRepository = comparisonRepository;
        this.archiveCandidateRegistrar = archiveCandidateRegistrar;
    }

    public void run(ReportComparisonTaskInput input, TaskExecutionContext context) {
        validate(input);
        context.publish(() -> { comparisonRepository.markRunning(input.comparisonRunId()); return null; });
        try {
            context.progress(10, "正在读取报告输入快照");
            ReportView baseReport = requireReport(input.baseReportId());
            ReportView targetReport = requireReport(input.targetReportId());
            if (!Objects.equals(baseReport.projectId(), input.projectId())
                    || !Objects.equals(targetReport.projectId(), input.projectId())) {
                throw new TaskExecutionException(TaskErrorCode.PROJECT_MISMATCH, "报告不属于当前项目", null);
            }

            List<ComparableInput> base = comparisonRepository.listAllInputs(baseReport.id()).stream()
                    .map(this::comparableInput)
                    .toList();
            List<ComparableInput> target = comparisonRepository.listAllInputs(targetReport.id()).stream()
                    .map(this::comparableInput)
                    .toList();
            if (base.isEmpty() || target.isEmpty()) {
                throw new TaskExecutionException(TaskErrorCode.REPORT_NO_CONFIRMED_INPUTS, "报告缺少可比较的输入快照", null);
            }

            context.progress(35, "正在匹配报告差异");
            List<ReportComparisonRepository.DiffItemCreateCommand> diffItems = diff(input.projectId(), base, target);
            Map<String, Object> summary = summary(baseReport, targetReport, base.size(), target.size(), diffItems);
            context.progress(80, "正在写入报告对比结果");
            context.publish(() -> {
            comparisonRepository.replaceDiffItems(input.projectId(), input.comparisonRunId(), diffItems);
            comparisonRepository.markSucceeded(input.comparisonRunId(), summary);
            comparisonRepository.findRun(input.comparisonRunId())
                    .ifPresent(run -> archiveCandidateRegistrar.registerReportComparison(run, targetReport.sourceRevisionId(), summary));
            return null;
            });
            context.progress(100, "报告对比完成");
        } catch (TaskAttemptLostException ex) {
            throw ex;
        } catch (RuntimeException ex) {
            context.publish(() -> {
            comparisonRepository.markFailed(input.comparisonRunId(), errorCode(ex), safeMessage(ex), Map.of(
                    "error", errorCode(ex),
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

    private void validate(ReportComparisonTaskInput input) {
        if (input == null
                || input.projectId() == null
                || input.comparisonRunId() == null
                || input.baseReportId() == null
                || input.targetReportId() == null) {
            throw new TaskExecutionException(TaskErrorCode.INPUT_INVALID, "报告对比任务输入非法", null);
        }
    }

    private ReportView requireReport(UUID reportId) {
        return reportRepository.findById(reportId)
                .orElseThrow(() -> new TaskExecutionException(TaskErrorCode.RESOURCE_NOT_FOUND, "报告不存在", null));
    }

    private ComparableInput comparableInput(ReportInputView input) {
        Map<String, Object> snapshot = input.inputSnapshot() == null ? Map.of() : input.inputSnapshot();
        Map<String, Object> detail = mapValue(snapshot.get("sourceDetail"));
        String sourceType = firstNonBlank(string(snapshot.get("sourceType")), input.inputType().name());
        String ruleId = firstNonBlank(string(snapshot.get("ruleId")), string(detail.get("ruleId")), string(detail.get("componentType")), sourceType);
        String path = firstNonBlank(string(snapshot.get("identityPath")), string(detail.get("filePath")), string(snapshot.get("filePath")), string(snapshot.get("locationLabel")), string(detail.get("sourcePackageName")), string(detail.get("sourceName")));
        String symbol = firstNonBlank(string(snapshot.get("identitySymbol")), string(detail.get("symbol")), string(detail.get("sourcePackageName")), string(detail.get("sourceName")));
        String anchor = firstNonBlank(string(snapshot.get("identityAnchor")), string(detail.get("fingerprint")), string(snapshot.get("fingerprint")), string(detail.get("title")), string(snapshot.get("issueTitle")));
        String fingerprint = firstNonBlank(string(snapshot.get("stableFingerprint")), string(detail.get("fingerprint")), stableFingerprint(sourceType, ruleId, normalizePath(path), normalize(symbol), normalize(anchor)));
        return new ComparableInput(
                input,
                snapshot,
                sourceType,
                ruleId,
                normalizePath(path),
                normalize(symbol),
                normalize(anchor),
                fingerprint
        );
    }

    private List<ReportComparisonRepository.DiffItemCreateCommand> diff(UUID projectId, List<ComparableInput> base, List<ComparableInput> target) {
        List<ReportComparisonRepository.DiffItemCreateCommand> result = new ArrayList<>();
        Map<String, ComparableInput> targetByFingerprint = target.stream()
                .filter(item -> !item.fingerprint().isBlank())
                .collect(Collectors.toMap(ComparableInput::fingerprint, Function.identity(), (left, right) -> left, LinkedHashMap::new));
        Set<UUID> matchedTargetIds = new HashSet<>();
        for (ComparableInput oldItem : base) {
            ComparableInput newItem = targetByFingerprint.get(oldItem.fingerprint());
            Match match = null;
            if (newItem != null && !matchedTargetIds.contains(newItem.input().id())) {
                match = new Match(newItem, "HIGH", "EXACT_FINGERPRINT");
            } else {
                match = fuzzyMatch(oldItem, target, matchedTargetIds);
            }
            if (match == null) {
                result.add(command(projectId, "RESOLVED", oldItem, null, null, "UNMATCHED_OLD"));
            } else {
                matchedTargetIds.add(match.item().input().id());
                result.add(command(projectId, changed(oldItem, match.item()) ? "CHANGED" : "UNCHANGED", oldItem, match.item(), match.confidence(), match.reason()));
            }
        }
        for (ComparableInput newItem : target) {
            if (!matchedTargetIds.contains(newItem.input().id())) {
                result.add(command(projectId, "NEW", null, newItem, null, "UNMATCHED_NEW"));
            }
        }
        return result;
    }

    private Match fuzzyMatch(ComparableInput oldItem, List<ComparableInput> target, Set<UUID> matchedTargetIds) {
        for (ComparableInput candidate : target) {
            if (matchedTargetIds.contains(candidate.input().id()) || !same(oldItem.sourceType(), candidate.sourceType())) {
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
            if (matchedTargetIds.contains(candidate.input().id()) || !same(oldItem.sourceType(), candidate.sourceType())) {
                continue;
            }
            if (same(oldItem.ruleId(), candidate.ruleId())
                    && same(oldItem.path(), candidate.path())
                    && same(oldItem.anchor(), candidate.anchor())) {
                return new Match(candidate, "MEDIUM", "SAME_RULE_PATH_ANCHOR");
            }
        }
        for (ComparableInput candidate : target) {
            if (matchedTargetIds.contains(candidate.input().id()) || !same(oldItem.sourceType(), candidate.sourceType())) {
                continue;
            }
            if (same(oldItem.ruleId(), candidate.ruleId()) && same(oldItem.anchor(), candidate.anchor())) {
                return new Match(candidate, "LOW", "SAME_RULE_ANCHOR");
            }
        }
        return null;
    }

    private ReportComparisonRepository.DiffItemCreateCommand command(
            UUID projectId,
            String diffStatus,
            ComparableInput oldItem,
            ComparableInput newItem,
            String matchConfidence,
            String matchReason
    ) {
        ComparableInput display = newItem == null ? oldItem : newItem;
        return new ReportComparisonRepository.DiffItemCreateCommand(
                display.sourceType(),
                oldItem == null ? null : oldItem.input().inputId(),
                newItem == null ? null : newItem.input().inputId(),
                diffStatus,
                firstNonBlank(value(display, "detectedLevel"), value(display, "riskLevel")),
                firstNonBlank(value(display, "issueTitle"), value(display, "title")),
                firstNonBlank(value(display, "locationLabel"), display.path()),
                firstNonBlank(value(display, "recommendationSummary"), value(display, "recommendation")),
                value(display, "confirmationStatus"),
                firstNonBlank(display.fingerprint(), oldItem == null ? null : oldItem.fingerprint(), newItem == null ? null : newItem.fingerprint()),
                matchConfidence,
                matchReason,
                oldItem == null ? null : oldItem.snapshot(),
                newItem == null ? null : newItem.snapshot()
        );
    }

    private boolean changed(ComparableInput oldItem, ComparableInput newItem) {
        return !Objects.equals(value(oldItem, "issueTitle"), value(newItem, "issueTitle"))
                || !Objects.equals(value(oldItem, "detectedLevel"), value(newItem, "detectedLevel"))
                || !Objects.equals(value(oldItem, "recommendationSummary"), value(newItem, "recommendationSummary"))
                || !Objects.equals(oldItem.path(), newItem.path())
                || !Objects.equals(oldItem.symbol(), newItem.symbol())
                || !Objects.equals(oldItem.anchor(), newItem.anchor());
    }

    private Map<String, Object> summary(
            ReportView baseReport,
            ReportView targetReport,
            int baseCount,
            int targetCount,
            List<ReportComparisonRepository.DiffItemCreateCommand> items
    ) {
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("baseReportId", baseReport.id());
        summary.put("targetReportId", targetReport.id());
        summary.put("baseSourceRevisionId", baseReport.sourceRevisionId());
        summary.put("targetSourceRevisionId", targetReport.sourceRevisionId());
        summary.put("baseInputCount", baseCount);
        summary.put("targetInputCount", targetCount);
        summary.put("total", items.size());
        summary.put("byStatus", grouped(items, ReportComparisonRepository.DiffItemCreateCommand::diffStatus));
        summary.put("bySourceType", grouped(items, ReportComparisonRepository.DiffItemCreateCommand::sourceType));
        summary.put("bySeverity", grouped(items, ReportComparisonRepository.DiffItemCreateCommand::severity));
        summary.put("byMatchConfidence", grouped(items, item -> item.matchConfidence() == null ? "UNMATCHED" : item.matchConfidence()));
        return summary;
    }

    private Map<String, Long> grouped(List<ReportComparisonRepository.DiffItemCreateCommand> items, Function<ReportComparisonRepository.DiffItemCreateCommand, String> classifier) {
        Map<String, Long> grouped = new LinkedHashMap<>();
        items.stream()
                .collect(Collectors.groupingBy(item -> firstNonBlank(classifier.apply(item), "UNKNOWN"), LinkedHashMap::new, Collectors.counting()))
                .forEach(grouped::put);
        return grouped;
    }

    private boolean same(String left, String right) {
        return !left.isBlank() && Objects.equals(left, right);
    }

    private String value(ComparableInput input, String key) {
        return input == null ? null : string(input.snapshot().get(key));
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

    private Map<String, Object> mapValue(Object value) {
        if (value instanceof Map<?, ?> map) {
            Map<String, Object> result = new LinkedHashMap<>();
            map.forEach((key, item) -> result.put(String.valueOf(key), item));
            return result;
        }
        return Map.of();
    }

    private String safeMessage(Throwable ex) {
        if (ex instanceof TaskExecutionException taskExecutionException) {
            return taskExecutionException.safeMessage();
        }
        return ex.getMessage() == null || ex.getMessage().isBlank() ? ex.getClass().getSimpleName() : ex.getMessage();
    }

    private String errorCode(Throwable ex) {
        if (ex instanceof TaskExecutionException taskExecutionException) {
            return taskExecutionException.errorCode();
        }
        return ERROR_CODE;
    }

    private record ComparableInput(
            ReportInputView input,
            Map<String, Object> snapshot,
            String sourceType,
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
