package cn.rvport.backend.migration;

import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.project.ProjectAccessService;
import cn.rvport.backend.source.SourceRevisionView;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class MigrationInputService {

    private final MigrationInputRepository migrationInputRepository;
    private final MigrationInputSourceResolver sourceResolver;
    private final ProjectAccessService projectAccessService;

    public MigrationInputService(
            MigrationInputRepository migrationInputRepository,
            MigrationInputSourceResolver sourceResolver,
            ProjectAccessService projectAccessService
    ) {
        this.migrationInputRepository = migrationInputRepository;
        this.sourceResolver = sourceResolver;
        this.projectAccessService = projectAccessService;
    }

    @Transactional(readOnly = true)
    public PageResponse<MigrationInputResponse> list(
            UUID projectId,
            UUID sourceRevisionId,
            MigrationInputListRequest request,
            UUID actorUserId,
            boolean superAdmin
    ) {
        projectAccessService.requireSourceRevisionAccess(projectId, sourceRevisionId, actorUserId, superAdmin);
        int page = request.normalizedPage();
        int pageSize = request.normalizedPageSize();
        try {
            List<MigrationInputRefView> filtered = filterList(currentRefsForSystem(projectId, sourceRevisionId), request);
            long total = filtered.size();
            List<MigrationInputResponse> items = filtered.stream()
                    .skip((long) (page - 1) * pageSize)
                    .limit(pageSize)
                    .map(MigrationInputResponse::from)
                    .toList();
            return PageResponse.of(items, page, pageSize, total);
        } catch (IllegalArgumentException ex) {
            throw badRequest("MIGRATION_INPUT_QUERY_INVALID", "迁移输入查询参数不正确");
        }
    }

    @Transactional
    public MigrationInputImportResponse importRefs(
            UUID projectId,
            UUID sourceRevisionId,
            MigrationInputImportRequest request,
            UUID actorUserId,
            boolean superAdmin
    ) {
        SourceRevisionView revision = projectAccessService.requireSourceRevisionAccess(projectId, sourceRevisionId, actorUserId, superAdmin);
        List<UUID> sourceRefIds = request.sourceRefIds();
        if (sourceRefIds == null || sourceRefIds.isEmpty()) {
            throw badRequest("MIGRATION_INPUT_IMPORT_EMPTY", "迁移输入来源不能为空");
        }
        UUID inputSetId = migrationInputRepository.ensureActiveSet(revision.projectId(), revision.id());
        List<MigrationInputCandidate> candidates = sourceRefIds.stream()
                .map(id -> sourceResolver.resolve(projectId, sourceRevisionId, request.sourceType(), id))
                .toList();
        MigrationInputRepository.InsertResult result = migrationInputRepository.insertCandidates(inputSetId, candidates);
        return new MigrationInputImportResponse(
                request.sourceType(),
                sourceRefIds.size(),
                result.createdItems().size(),
                result.skipped(),
                result.createdItems().stream().map(MigrationInputResponse::from).toList()
        );
    }

    @Transactional
    public MigrationInputAutoMergeResponse autoMerge(
            UUID projectId,
            UUID sourceRevisionId,
            MigrationInputAutoMergeRequest request,
            UUID actorUserId,
            boolean superAdmin
    ) {
        projectAccessService.requireSourceRevisionAccess(projectId, sourceRevisionId, actorUserId, superAdmin);
        throw badRequest("MIGRATION_INPUT_AUTO_MERGE_DEPRECATED", "迁移输入自动合并已废弃，请在各分析节点内确认结果");
    }

    @Transactional
    public MigrationInputRepository.InsertResult syncSourceRefs(
            UUID projectId,
            UUID sourceRevisionId,
            MigrationInputSourceType sourceType,
            List<UUID> sourceRefIds
    ) {
        migrationInputRepository.deleteBySourceType(projectId, sourceRevisionId, sourceType);
        if (sourceRefIds == null || sourceRefIds.isEmpty()) {
            return new MigrationInputRepository.InsertResult(List.of(), 0);
        }
        UUID inputSetId = migrationInputRepository.ensureActiveSet(projectId, sourceRevisionId);
        List<MigrationInputCandidate> candidates = sourceRefIds.stream()
                .distinct()
                .map(id -> sourceResolver.resolve(projectId, sourceRevisionId, sourceType, id))
                .toList();
        return migrationInputRepository.insertCandidates(inputSetId, candidates);
    }

    @Transactional
    public MigrationInputAutoMergeResponse autoMergeDeprecated(
            UUID projectId,
            UUID sourceRevisionId,
            MigrationInputAutoMergeRequest request,
            UUID actorUserId,
            boolean superAdmin
    ) {
        SourceRevisionView revision = projectAccessService.requireSourceRevisionAccess(projectId, sourceRevisionId, actorUserId, superAdmin);
        UUID inputSetId = migrationInputRepository.ensureActiveSet(revision.projectId(), revision.id());
        List<MigrationInputAutoMergeResponse.SourceResult> sourceResults = new ArrayList<>();
        int totalCreated = 0;
        int totalSkipped = 0;
        int totalNoResult = 0;
        for (MigrationInputSourceType sourceType : autoMergeSources(request)) {
            List<UUID> sourceRefIds = sourceResolver.latestSourceRefIds(projectId, sourceRevisionId, sourceType);
            if (sourceRefIds.isEmpty()) {
                sourceResults.add(new MigrationInputAutoMergeResponse.SourceResult(sourceType, 0, 0, 0, true));
                totalNoResult++;
                continue;
            }
            List<MigrationInputCandidate> candidates = sourceRefIds.stream()
                    .map(id -> sourceResolver.resolve(projectId, sourceRevisionId, sourceType, id))
                    .toList();
            MigrationInputRepository.InsertResult result = migrationInputRepository.insertCandidates(inputSetId, candidates);
            int created = result.createdItems().size();
            totalCreated += created;
            totalSkipped += result.skipped();
            sourceResults.add(new MigrationInputAutoMergeResponse.SourceResult(sourceType, candidates.size(), created, result.skipped(), false));
        }
        return new MigrationInputAutoMergeResponse(totalCreated, totalSkipped, totalNoResult, sourceResults);
    }

    @Transactional(readOnly = true)
    public MigrationInputDetailResponse detail(UUID migrationInputId, UUID actorUserId, boolean superAdmin) {
        MigrationInputRefView ref = requireAccessibleRef(migrationInputId, actorUserId, superAdmin);
        return new MigrationInputDetailResponse(MigrationInputResponse.from(ref), sourceResolver.detail(ref));
    }

    @Transactional
    public MigrationInputResponse update(UUID migrationInputId, MigrationInputUpdateRequest request, UUID actorUserId, boolean superAdmin) {
        requireAccessibleRef(migrationInputId, actorUserId, superAdmin);
        if (request.status() == null && request.note() == null) {
            throw badRequest("MIGRATION_INPUT_UPDATE_EMPTY", "迁移输入更新内容不能为空");
        }
        MigrationInputRefView updated = migrationInputRepository.update(migrationInputId, request.status(), request.note());
        if (updated == null) {
            throw notFound("MIGRATION_INPUT_NOT_FOUND", "迁移输入不存在");
        }
        return MigrationInputResponse.from(updated);
    }

    public List<MigrationInputRefView> confirmedRefs(UUID projectId, UUID sourceRevisionId, UUID actorUserId, boolean superAdmin) {
        projectAccessService.requireSourceRevisionAccess(projectId, sourceRevisionId, actorUserId, superAdmin);
        return currentConfirmedRefsForSystem(projectId, sourceRevisionId);
    }

    @Transactional(readOnly = true, isolation = org.springframework.transaction.annotation.Isolation.REPEATABLE_READ)
    public List<MigrationInputRefView> currentRefsForSystem(UUID projectId, UUID sourceRevisionId) {
        return currentEffectiveRefs(projectId, sourceRevisionId, migrationInputRepository.listAll(projectId, sourceRevisionId));
    }

    @Transactional(readOnly = true, isolation = org.springframework.transaction.annotation.Isolation.REPEATABLE_READ)
    public List<MigrationInputRefView> currentConfirmedRefsForSystem(UUID projectId, UUID sourceRevisionId) {
        return currentRefsForSystem(projectId, sourceRevisionId)
                .stream()
                .filter(ref -> ref.status() == MigrationInputStatus.CONFIRMED)
                .toList();
    }

    private MigrationInputRefView requireAccessibleRef(UUID migrationInputId, UUID actorUserId, boolean superAdmin) {
        MigrationInputRefView ref = migrationInputRepository.findById(migrationInputId)
                .orElseThrow(() -> notFound("MIGRATION_INPUT_NOT_FOUND", "迁移输入不存在"));
        projectAccessService.requireSourceRevisionAccess(ref.projectId(), ref.sourceRevisionId(), actorUserId, superAdmin);
        return ref;
    }

    private List<MigrationInputSourceType> autoMergeSources(MigrationInputAutoMergeRequest request) {
        if (request == null || request.sourceTypes() == null || request.sourceTypes().isEmpty()) {
            return List.of(MigrationInputSourceType.KB_FINDING, MigrationInputSourceType.DEPENDENCY_RESULT);
        }
        return request.sourceTypes().stream()
                .distinct()
                .toList();
    }

    private List<MigrationInputRefView> filterList(List<MigrationInputRefView> refs, MigrationInputListRequest request) {
        return refs.stream()
                .filter(ref -> request.sourceType() == null || ref.sourceType() == request.sourceType())
                .filter(ref -> request.status() == null || ref.status() == request.status())
                .filter(ref -> request.detectedLevel() == null || request.detectedLevel().isBlank()
                        || ref.detectedLevel().equals(request.detectedLevel().trim()))
                .filter(ref -> matchesKeyword(ref, request.keyword()))
                .sorted(listComparator(request))
                .toList();
    }

    private boolean matchesKeyword(MigrationInputRefView ref, String keyword) {
        if (keyword == null || keyword.isBlank()) {
            return true;
        }
        String text = keyword.trim().toLowerCase(Locale.ROOT);
        return contains(ref.issueTitle(), text)
                || contains(ref.locationLabel(), text)
                || contains(ref.recommendationSummary(), text);
    }

    private boolean contains(String value, String keyword) {
        return value != null && value.toLowerCase(Locale.ROOT).contains(keyword);
    }

    private Comparator<MigrationInputRefView> listComparator(MigrationInputListRequest request) {
        String sortBy = request.sortBy() == null ? "" : request.sortBy().trim();
        boolean desc = "desc".equalsIgnoreCase(request.sortDirection());
        Comparator<MigrationInputRefView> comparator = switch (sortBy) {
            case "createdAt", "" -> Comparator.comparing(MigrationInputRefView::createdAt, Comparator.nullsLast(Comparator.naturalOrder()));
            case "updatedAt" -> Comparator.comparing(MigrationInputRefView::updatedAt, Comparator.nullsLast(Comparator.naturalOrder()));
            case "sourceType" -> Comparator.comparing(ref -> ref.sourceType().name(), Comparator.nullsLast(String::compareTo));
            case "detectedLevel" -> Comparator.comparing(MigrationInputRefView::detectedLevel, Comparator.nullsLast(String::compareTo));
            case "status" -> Comparator.comparing(ref -> ref.status().name(), Comparator.nullsLast(String::compareTo));
            case "issueTitle" -> Comparator.comparing(MigrationInputRefView::issueTitle, Comparator.nullsLast(String::compareToIgnoreCase));
            default -> throw new IllegalArgumentException("Unsupported migration input sort field: " + request.sortBy());
        };
        comparator = desc || sortBy.isBlank() ? comparator.reversed() : comparator;
        return comparator.thenComparing(MigrationInputRefView::id);
    }

    private List<MigrationInputRefView> currentEffectiveRefs(UUID projectId, UUID sourceRevisionId, List<MigrationInputRefView> refs) {
        if (refs == null || refs.isEmpty()) {
            return List.of();
        }
        List<UUID> latestDependencySourceRefIds = sourceResolver.latestSourceRefIds(
                projectId,
                sourceRevisionId,
                MigrationInputSourceType.DEPENDENCY_RESULT
        );
        Set<UUID> latestDependencyRefIds = latestDependencySourceRefIds == null ? Set.of() : Set.copyOf(latestDependencySourceRefIds);
        Set<UUID> latestKbRefIds = Set.copyOf(sourceResolver.latestSourceRefIds(projectId, sourceRevisionId,
                MigrationInputSourceType.KB_FINDING));
        Map<String, MigrationInputRefView> byKey = new LinkedHashMap<>();
        for (MigrationInputRefView ref : refs) {
            if (ref.sourceType() == MigrationInputSourceType.KB_FINDING && !latestKbRefIds.contains(ref.sourceRefId())) continue;
            if (ref.sourceType() == MigrationInputSourceType.DEPENDENCY_RESULT
                    && !latestDependencyRefIds.contains(ref.sourceRefId())) {
                continue;
            }
            String key = currentEffectiveKey(ref);
            MigrationInputRefView existing = byKey.get(key);
            if (existing == null || prefer(ref, existing)) {
                byKey.put(key, ref);
            }
        }
        return List.copyOf(byKey.values());
    }

    private String currentEffectiveKey(MigrationInputRefView ref) {
        if (ref.sourceType() != MigrationInputSourceType.DEPENDENCY_RESULT) {
            return ref.id().toString();
        }
        String dependencyType = normalize(ref.ruleId());
        String dependencyName = normalize(firstNonBlank(ref.identityPath(), ref.identitySymbol(), ref.issueTitle()));
        return ref.sourceType().name() + "|" + dependencyType + "|" + dependencyName;
    }

    private boolean prefer(MigrationInputRefView candidate, MigrationInputRefView existing) {
        int candidateStatus = statusRank(candidate.status());
        int existingStatus = statusRank(existing.status());
        if (candidateStatus != existingStatus) {
            return candidateStatus < existingStatus;
        }
        int candidateRisk = riskRank(candidate.detectedLevel());
        int existingRisk = riskRank(existing.detectedLevel());
        if (candidateRisk != existingRisk) {
            return candidateRisk < existingRisk;
        }
        if (candidate.updatedAt() != null && existing.updatedAt() != null) {
            return candidate.updatedAt().isAfter(existing.updatedAt());
        }
        if (candidate.createdAt() != null && existing.createdAt() != null) {
            return candidate.createdAt().isAfter(existing.createdAt());
        }
        return false;
    }

    private int statusRank(MigrationInputStatus status) {
        if (status == MigrationInputStatus.EXCLUDED) {
            return 0;
        }
        if (status == MigrationInputStatus.CONFIRMED) {
            return 1;
        }
        if (status == MigrationInputStatus.CANDIDATE) {
            return 2;
        }
        return 3;
    }

    private int riskRank(String detectedLevel) {
        String risk = MigrationInputRiskPolicy.normalizeRiskToken(detectedLevel);
        return switch (risk) {
            case "CRITICAL" -> 0;
            case "HIGH" -> 1;
            case "MEDIUM" -> 2;
            case "LOW" -> 3;
            case "INFO" -> 4;
            default -> 5;
        };
    }

    private String normalize(String value) {
        return value == null || value.isBlank() ? "" : value.trim().toLowerCase(Locale.ROOT);
    }

    private String firstNonBlank(String... values) {
        for (String value : values) {
            if (value != null && !value.isBlank()) {
                return value.trim();
            }
        }
        return "";
    }

    private ApiException notFound(String code, String message) {
        return new ApiException(HttpStatus.NOT_FOUND, code, message);
    }

    private ApiException badRequest(String code, String message) {
        return new ApiException(HttpStatus.BAD_REQUEST, code, message);
    }
}
