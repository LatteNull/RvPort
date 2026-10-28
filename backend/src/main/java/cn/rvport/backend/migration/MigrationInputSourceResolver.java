package cn.rvport.backend.migration;

import cn.rvport.backend.analysis.SpecializedAnalysisFindingView;
import cn.rvport.backend.analysis.SpecializedAnalysisRepository;
import cn.rvport.backend.analysis.SpecializedAnalysisRunView;
import cn.rvport.backend.analysis.SpecializedAnalyzerType;
import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.dependency.DependencyAnalysisRepository;
import cn.rvport.backend.dependency.DependencyAnalysisResultItemView;
import cn.rvport.backend.dependency.DependencyAnalysisView;
import cn.rvport.backend.kb.FindingView;
import cn.rvport.backend.kb.ai.KbAiExtensionRepository;
import cn.rvport.backend.kb.KbScanRepository;
import cn.rvport.backend.kb.KbScanView;
import cn.rvport.backend.task.TaskStatus;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Service
public class MigrationInputSourceResolver {

    private final KbScanRepository kbScanRepository;
    private final DependencyAnalysisRepository dependencyAnalysisRepository;
    private final KbAiExtensionRepository kbAiExtensionRepository;
    private final SpecializedAnalysisRepository specializedAnalysisRepository;

    @Autowired
    public MigrationInputSourceResolver(
            KbScanRepository kbScanRepository,
            DependencyAnalysisRepository dependencyAnalysisRepository,
            KbAiExtensionRepository kbAiExtensionRepository,
            SpecializedAnalysisRepository specializedAnalysisRepository
    ) {
        this.kbScanRepository = kbScanRepository;
        this.dependencyAnalysisRepository = dependencyAnalysisRepository;
        this.kbAiExtensionRepository = kbAiExtensionRepository;
        this.specializedAnalysisRepository = specializedAnalysisRepository;
    }

    MigrationInputSourceResolver(
            KbScanRepository kbScanRepository,
            DependencyAnalysisRepository dependencyAnalysisRepository
    ) {
        this(kbScanRepository, dependencyAnalysisRepository, null, null);
    }

    MigrationInputCandidate resolve(UUID projectId, UUID sourceRevisionId, MigrationInputSourceType sourceType, UUID sourceRefId) {
        return switch (sourceType) {
            case KB_FINDING -> resolveKbFinding(projectId, sourceRevisionId, sourceRefId);
            case DEPENDENCY_RESULT -> resolveDependencyResult(projectId, sourceRevisionId, sourceRefId);
            case FLOATING_POINT_FINDING, MEMORY_ORDER_FINDING -> resolveSpecializedFinding(
                    projectId, sourceRevisionId, sourceType, sourceRefId);
        };
    }

    List<UUID> latestSourceRefIds(UUID projectId, UUID sourceRevisionId, MigrationInputSourceType sourceType) {
        return switch (sourceType) {
            case KB_FINDING -> kbScanRepository.findLatestSucceededRunBySourceRevision(projectId, sourceRevisionId)
                    .map(KbScanView::id)
                    .map(kbScanRepository::listFindingIds)
                    .orElseGet(List::of);
            case DEPENDENCY_RESULT -> dependencyAnalysisRepository.findLatestSucceededRun(projectId, sourceRevisionId)
                    .filter(run -> run.status() == TaskStatus.SUCCEEDED)
                    .map(DependencyAnalysisView::id)
                    .map(dependencyAnalysisRepository::listResultItemIds)
                    .orElseGet(List::of);
            case FLOATING_POINT_FINDING, MEMORY_ORDER_FINDING -> specializedAnalysisRepository == null ? List.of()
                    : specializedAnalysisRepository.latestPublished(projectId, sourceRevisionId, analyzerType(sourceType))
                            .map(SpecializedAnalysisRunView::id)
                            .map(specializedAnalysisRepository::listFindingIds)
                            .orElseGet(List::of);
        };
    }

    public Map<String, Object> detail(MigrationInputRefView ref) {
        return switch (ref.sourceType()) {
            case KB_FINDING -> kbFindingDetail(ref.sourceRefId());
            case DEPENDENCY_RESULT -> dependencyResultDetail(ref.sourceRefId());
            case FLOATING_POINT_FINDING, MEMORY_ORDER_FINDING -> specializedFindingDetail(ref.sourceRefId());
        };
    }

    public Map<String, Object> memoryOrderAnalysisSummary(UUID projectId, UUID sourceRevisionId) {
        if (specializedAnalysisRepository == null) return Map.of("analysisStatus", "UNAVAILABLE");
        return specializedAnalysisRepository.latestPublished(projectId, sourceRevisionId, SpecializedAnalyzerType.MEMORY_ORDER)
                .map(run -> {
                    Map<String, Object> value = new LinkedHashMap<>(
                            cn.rvport.backend.analysis.MemoryOrderResultPolicy.historicalSummary(run.summary()));
                    value.put("analysisStatus", run.status().name());
                    value.put("verdict", run.verdict());
                    value.put("runId", run.id());
                    value.put("limitations", "结论受已提供的证据和模型限制；零正式风险不代表迁移安全");
                    value.put("limitationsEn", "Conclusions are limited by available evidence and models; zero formal findings does not establish migration safety");
                    return value;
                }).orElseGet(() -> Map.of("analysisStatus", "UNAVAILABLE"));
    }

    private MigrationInputCandidate resolveSpecializedFinding(
            UUID projectId,
            UUID sourceRevisionId,
            MigrationInputSourceType sourceType,
            UUID findingId
    ) {
        SpecializedAnalysisFindingView finding = requireSpecializedFinding(findingId);
        if (!Objects.equals(finding.projectId(), projectId)) {
            throw notFound("MIGRATION_INPUT_SOURCE_NOT_FOUND", "迁移输入来源不存在");
        }
        if (!Objects.equals(finding.sourceRevisionId(), sourceRevisionId)
                || finding.analyzerType() != analyzerType(sourceType)) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "MIGRATION_INPUT_SOURCE_REVISION_MISMATCH",
                    "专项分析 Finding 不属于当前源码版本或分析类型");
        }
        String detectedLevel = MigrationInputRiskPolicy.normalizedDetectedLevel(finding.severity());
        boolean pending = finding.analyzerType() == SpecializedAnalyzerType.MEMORY_ORDER
                && cn.rvport.backend.analysis.MemoryOrderResultPolicy.pending(
                    cn.rvport.backend.analysis.MemoryOrderResultPolicy.kind(finding.findingKind(), finding.detail()));
        return new MigrationInputCandidate(
                projectId,
                sourceRevisionId,
                defaultText(finding.title(), finding.findingCode()),
                sourceType,
                finding.id(),
                detectedLevel,
                specializedLocationLabel(finding),
                firstNonBlank(finding.suggestion(), finding.testSuggestion(), finding.message()),
                finding.findingCode(),
                finding.filePath(),
                firstNonBlank(finding.category(), finding.findingKind()),
                firstNonBlank(finding.semanticDigest(), finding.externalFindingId()),
                stableFingerprint(sourceType.name(), finding.findingCode(), normalizePath(finding.filePath()),
                        String.valueOf(finding.startLine()), firstNonBlank(finding.semanticDigest(), finding.externalFindingId())),
                pending ? MigrationInputStatus.CANDIDATE : MigrationInputRiskPolicy.defaultStatus(detectedLevel)
        );
    }

    private Map<String, Object> specializedFindingDetail(UUID findingId) {
        SpecializedAnalysisFindingView finding = requireSpecializedFinding(findingId);
        Map<String, Object> detail = new LinkedHashMap<>();
        detail.put("id", finding.id());
        detail.put("runId", finding.runId());
        detail.put("projectId", finding.projectId());
        detail.put("sourceRevisionId", finding.sourceRevisionId());
        detail.put("analyzerType", finding.analyzerType());
        detail.put("externalFindingId", finding.externalFindingId());
        detail.put("findingKind", finding.findingKind());
        detail.put("findingCode", finding.findingCode());
        detail.put("category", finding.category());
        detail.put("severity", finding.severity());
        detail.put("confidence", finding.confidence());
        detail.put("resultStatus", finding.resultStatus());
        detail.put("title", finding.title());
        detail.put("titleEn", finding.titleEn());
        detail.put("message", finding.message());
        detail.put("messageEn", finding.messageEn());
        detail.put("suggestion", finding.suggestion());
        detail.put("suggestionEn", finding.suggestionEn());
        detail.put("testSuggestion", finding.testSuggestion());
        detail.put("testSuggestionEn", finding.testSuggestionEn());
        detail.put("filePath", finding.filePath());
        detail.put("startLine", finding.startLine());
        detail.put("startColumn", finding.startColumn());
        detail.put("endLine", finding.endLine());
        detail.put("endColumn", finding.endColumn());
        detail.put("requiresHumanConfirmation", finding.requiresHumanConfirmation());
        detail.put("semanticDigest", finding.semanticDigest());
        detail.put("analysisDetail", finding.detail());
        if (finding.analyzerType() == SpecializedAnalyzerType.MEMORY_ORDER) {
            String kind = cn.rvport.backend.analysis.MemoryOrderResultPolicy.kind(finding.findingKind(), finding.detail());
            detail.put("findingKind", kind);
            detail.put("pendingVerification", cn.rvport.backend.analysis.MemoryOrderResultPolicy.pending(kind));
        }
        detail.put("createdAt", finding.createdAt());
        return detail;
    }

    private SpecializedAnalysisFindingView requireSpecializedFinding(UUID findingId) {
        if (specializedAnalysisRepository == null) {
            throw notFound("MIGRATION_INPUT_SOURCE_NOT_FOUND", "专项分析迁移输入来源不可用");
        }
        return specializedAnalysisRepository.findFinding(findingId)
                .orElseThrow(() -> notFound("MIGRATION_INPUT_SOURCE_NOT_FOUND", "迁移输入来源不存在"));
    }

    private String specializedLocationLabel(SpecializedAnalysisFindingView finding) {
        String path = defaultText(finding.filePath(), "unknown");
        if (finding.startLine() == null) return path;
        if (finding.endLine() == null || Objects.equals(finding.startLine(), finding.endLine())) {
            return path + ":" + finding.startLine();
        }
        return path + ":" + finding.startLine() + "-" + finding.endLine();
    }

    private SpecializedAnalyzerType analyzerType(MigrationInputSourceType sourceType) {
        return sourceType == MigrationInputSourceType.FLOATING_POINT_FINDING
                ? SpecializedAnalyzerType.FLOATING_POINT : SpecializedAnalyzerType.MEMORY_ORDER;
    }

    private MigrationInputCandidate resolveKbFinding(UUID projectId, UUID sourceRevisionId, UUID findingId) {
        FindingView finding = kbScanRepository.findFinding(findingId)
                .orElseThrow(() -> notFound("MIGRATION_INPUT_SOURCE_NOT_FOUND", "迁移输入来源不存在"));
        if (!Objects.equals(finding.projectId(), projectId)) {
            throw notFound("MIGRATION_INPUT_SOURCE_NOT_FOUND", "迁移输入来源不存在");
        }
        if (!Objects.equals(finding.sourceRevisionId(), sourceRevisionId)) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "MIGRATION_INPUT_SOURCE_REVISION_MISMATCH", "KB finding 不属于当前源码版本");
        }
        String detectedLevel = MigrationInputRiskPolicy.normalizedDetectedLevel(finding.severity());
        return new MigrationInputCandidate(
                projectId,
                sourceRevisionId,
                defaultText(finding.title(), finding.ruleId()),
                MigrationInputSourceType.KB_FINDING,
                finding.id(),
                detectedLevel,
                kbLocationLabel(finding),
                finding.suggestion(),
                finding.ruleId(),
                finding.filePath(),
                finding.symbol(),
                kbAnchor(finding),
                stableFingerprint(
                        MigrationInputSourceType.KB_FINDING.name(),
                        finding.ruleId(),
                        normalizePath(finding.filePath()),
                        normalizeText(finding.symbol()),
                        normalizeText(kbAnchor(finding))
                ),
                MigrationInputRiskPolicy.defaultStatus(detectedLevel)
        );
    }

    private MigrationInputCandidate resolveDependencyResult(UUID projectId, UUID sourceRevisionId, UUID resultItemId) {
        DependencyAnalysisResultItemView item = dependencyAnalysisRepository.findResultItem(resultItemId)
                .orElseThrow(() -> notFound("MIGRATION_INPUT_SOURCE_NOT_FOUND", "迁移输入来源不存在"));
        if (!Objects.equals(item.projectId(), projectId)) {
            throw notFound("MIGRATION_INPUT_SOURCE_NOT_FOUND", "迁移输入来源不存在");
        }
        if (!Objects.equals(item.sourceRevisionId(), sourceRevisionId)) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "MIGRATION_INPUT_SOURCE_REVISION_MISMATCH", "依赖分析结果不属于当前源码版本");
        }
        String detectedLevel = MigrationInputRiskPolicy.normalizedDetectedLevel(item.riskLevel().name(), item.targetMatchStatus().name());
        return new MigrationInputCandidate(
                projectId,
                sourceRevisionId,
                dependencyIssueTitle(item),
                MigrationInputSourceType.DEPENDENCY_RESULT,
                item.id(),
                detectedLevel,
                dependencyLocationLabel(item),
                item.recommendation(),
                item.dependencyType().name(),
                item.dependencyName(),
                item.dependencyName(),
                firstNonBlank(item.dependencyVersion(), item.targetMatchStatus().name()),
                stableFingerprint(
                        MigrationInputSourceType.DEPENDENCY_RESULT.name(),
                        item.dependencyType().name(),
                        normalizeText(item.dependencyName()),
                        normalizeText(item.dependencyVersion()),
                        item.targetMatchStatus().name()
                ),
                MigrationInputRiskPolicy.defaultStatus(detectedLevel)
        );
    }

    private Map<String, Object> kbFindingDetail(UUID findingId) {
        FindingView finding = kbScanRepository.findFinding(findingId)
                .orElseThrow(() -> notFound("MIGRATION_INPUT_SOURCE_NOT_FOUND", "迁移输入来源不存在"));
        Map<String, Object> detail = new LinkedHashMap<>();
        detail.put("id", finding.id());
        detail.put("projectId", finding.projectId());
        detail.put("scanRunId", finding.scanRunId());
        detail.put("sourceRevisionId", finding.sourceRevisionId());
        detail.put("ruleId", finding.ruleId());
        detail.put("category", finding.category());
        detail.put("severity", finding.severity());
        detail.put("title", finding.title());
        detail.put("description", finding.description());
        detail.put("filePath", finding.filePath());
        detail.put("lineStart", finding.lineStart());
        detail.put("lineEnd", finding.lineEnd());
        detail.put("symbol", finding.symbol());
        detail.put("evidence", finding.evidence());
        detail.put("suggestion", finding.suggestion());
        if (kbAiExtensionRepository != null) {
            kbAiExtensionRepository.latestSuggestion(finding.scanRunId(), finding.id())
                    .ifPresent(suggestion -> detail.put("aiExtension", suggestion));
        }
        detail.put("status", finding.status());
        detail.put("createdAt", finding.createdAt());
        return detail;
    }

    private Map<String, Object> dependencyResultDetail(UUID resultItemId) {
        DependencyAnalysisResultItemView item = dependencyAnalysisRepository.findResultItem(resultItemId)
                .orElseThrow(() -> notFound("MIGRATION_INPUT_SOURCE_NOT_FOUND", "迁移输入来源不存在"));
        Map<String, Object> detail = new LinkedHashMap<>();
        detail.put("id", item.id());
        detail.put("projectId", item.projectId());
        detail.put("taskId", item.taskId());
        detail.put("dependencyAnalysisRunId", item.dependencyAnalysisRunId());
        detail.put("sourceRevisionId", item.sourceRevisionId());
        detail.put("dependencyType", item.dependencyType());
        detail.put("dependencyName", item.dependencyName());
        detail.put("dependencyVersion", item.dependencyVersion());
        detail.put("sourceProviderPackage", item.sourceProviderPackage());
        detail.put("sourceProviderVersion", item.sourceProviderVersion());
        detail.put("sourceDetectedVersion", item.sourceDetectedVersion());
        detail.put("targetProviderPackage", item.targetProviderPackage());
        detail.put("targetProviderVersion", item.targetProviderVersion());
        detail.put("targetDetectedVersion", item.targetDetectedVersion());
        detail.put("providerVersionStatus", item.providerVersionStatus());
        detail.put("versionEvidenceConfidence", item.versionEvidenceConfidence());
        detail.put("targetMatchStatus", item.targetMatchStatus());
        detail.put("riskLevel", item.riskLevel());
        detail.put("locationLabel", item.locationLabel());
        detail.put("recommendation", item.recommendation());
        detail.put("confidence", item.confidence());
        detail.put("evidence", item.evidence());
        detail.put("createdAt", item.createdAt());
        return detail;
    }

    private String kbLocationLabel(FindingView finding) {
        String path = defaultText(finding.filePath(), "unknown");
        if (finding.lineStart() == null) {
            return path;
        }
        if (finding.lineEnd() == null || Objects.equals(finding.lineStart(), finding.lineEnd())) {
            return path + ":" + finding.lineStart();
        }
        return path + ":" + finding.lineStart() + "-" + finding.lineEnd();
    }

    private String dependencyIssueTitle(DependencyAnalysisResultItemView item) {
        return item.dependencyName() + " 依赖可用性分析";
    }

    private String dependencyLocationLabel(DependencyAnalysisResultItemView item) {
        if (item.locationLabel() != null && !item.locationLabel().isBlank()) {
            return item.locationLabel();
        }
        return switch (item.dependencyType()) {
            case BUILD_TOOL -> "build:" + item.dependencyName();
            case BUILD_PACKAGE, TEST_PACKAGE -> "package:" + item.dependencyName() + versionSuffix(item.dependencyVersion());
            case LINK_LIBRARY, RUNTIME_LIBRARY -> "lib:" + item.dependencyName();
            case TEST_TOOL -> "test:" + item.dependencyName();
        };
    }

    private String kbAnchor(FindingView finding) {
        Object anchor = firstEvidenceValue(finding.evidence(), "anchor", "normalizedAnchor", "code", "snippet", "matchedText", "evidence");
        return firstNonBlank(anchor == null ? null : String.valueOf(anchor), finding.fingerprint(), finding.title());
    }

    private Object firstEvidenceValue(Map<String, Object> evidence, String... keys) {
        if (evidence == null || evidence.isEmpty()) {
            return null;
        }
        for (String key : keys) {
            Object value = evidence.get(key);
            if (value != null && !String.valueOf(value).isBlank()) {
                return value;
            }
        }
        return null;
    }

    private String stableFingerprint(String... parts) {
        String joined = String.join("|", java.util.Arrays.stream(parts)
                .map(this::normalizeText)
                .toList());
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return HexFormat.of().formatHex(digest.digest(joined.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 is not available", ex);
        }
    }

    private String normalizePath(String value) {
        return normalizeText(value).replace('\\', '/');
    }

    private String normalizeText(String value) {
        return value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
    }

    private String versionSuffix(String version) {
        return version == null || version.isBlank() ? "" : "@" + version.trim();
    }

    private String firstNonBlank(String... values) {
        List<String> candidates = new ArrayList<>();
        for (String value : values) {
            if (value != null && !value.isBlank()) {
                candidates.add(value.trim());
            }
        }
        return candidates.isEmpty() ? "unknown" : candidates.get(0);
    }

    private String defaultText(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value.trim();
    }

    private ApiException notFound(String code, String message) {
        return new ApiException(HttpStatus.NOT_FOUND, code, message);
    }
}
