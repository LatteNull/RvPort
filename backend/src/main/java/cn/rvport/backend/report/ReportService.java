package cn.rvport.backend.report;

import cn.rvport.backend.artifact.StoredArtifactOwnerType;
import cn.rvport.backend.artifact.StoredArtifactRepository;
import cn.rvport.backend.artifact.StoredArtifactResource;
import cn.rvport.backend.artifact.StoredArtifactService;
import cn.rvport.backend.artifact.StoredArtifactView;
import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.migration.MigrationInputRefView;
import cn.rvport.backend.migration.MigrationInputRiskPolicy;
import cn.rvport.backend.migration.MigrationInputService;
import cn.rvport.backend.migration.MigrationInputStatus;
import cn.rvport.backend.project.ProjectAccessService;
import cn.rvport.backend.reportcomparison.ReportComparisonRepository;
import cn.rvport.backend.reportcomparison.ReportComparisonSummaryResponse;
import cn.rvport.backend.source.SourceRepository;
import cn.rvport.backend.source.SourceRevisionView;
import cn.rvport.backend.task.RvPortTaskTypes;
import cn.rvport.backend.task.TaskCreateCommand;
import cn.rvport.backend.task.TaskRepository;
import cn.rvport.backend.task.TaskResponse;
import cn.rvport.backend.task.TaskService;
import cn.rvport.backend.workflow.DomainLatestExecutionResponse;
import cn.rvport.backend.workflow.DomainLatestResponse;
import cn.rvport.backend.workflow.ProjectContextService;
import cn.rvport.backend.workflow.ProjectContextSnapshot;
import cn.rvport.backend.workflow.StageIds;
import cn.rvport.backend.workflow.StagePrerequisiteKeys;
import cn.rvport.backend.workflow.StageReadinessService;
import jakarta.servlet.http.HttpServletRequest;
import java.util.LinkedHashMap;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ReportService {

    private final ReportRepository reportRepository;
    private final SourceRepository sourceRepository;
    private final ProjectAccessService projectAccessService;
    private final TaskService taskService;
    private final TaskRepository taskRepository;
    private final ProjectContextService projectContextService;
    private final StageReadinessService stageReadinessService;
    private final StoredArtifactRepository storedArtifactRepository;
    private final StoredArtifactService storedArtifactService;
    private final ReportComparisonRepository reportComparisonRepository;
    private final MigrationInputService migrationInputService;

    @Autowired
    public ReportService(
            ReportRepository reportRepository,
            SourceRepository sourceRepository,
            ProjectAccessService projectAccessService,
            TaskService taskService,
            TaskRepository taskRepository,
            ProjectContextService projectContextService,
            StageReadinessService stageReadinessService,
            StoredArtifactRepository storedArtifactRepository,
            StoredArtifactService storedArtifactService,
            ReportComparisonRepository reportComparisonRepository,
            MigrationInputService migrationInputService
    ) {
        this.reportRepository = reportRepository;
        this.sourceRepository = sourceRepository;
        this.projectAccessService = projectAccessService;
        this.taskService = taskService;
        this.taskRepository = taskRepository;
        this.projectContextService = projectContextService;
        this.stageReadinessService = stageReadinessService;
        this.storedArtifactRepository = storedArtifactRepository;
        this.storedArtifactService = storedArtifactService;
        this.reportComparisonRepository = reportComparisonRepository;
        this.migrationInputService = migrationInputService;
    }

    ReportService(
            ReportRepository reportRepository,
            SourceRepository sourceRepository,
            ProjectAccessService projectAccessService,
            TaskService taskService,
            StoredArtifactRepository storedArtifactRepository,
            StoredArtifactService storedArtifactService,
            ReportComparisonRepository reportComparisonRepository,
            MigrationInputService migrationInputService
    ) {
        this(reportRepository, sourceRepository, projectAccessService, taskService, null, null, null,
                storedArtifactRepository, storedArtifactService, reportComparisonRepository, migrationInputService);
    }

    @Transactional
    public TaskResponse createEvaluation(UUID projectId, ReportGenerateRequest request, UUID actorUserId, boolean superAdmin, HttpServletRequest httpRequest) {
        projectAccessService.requireProjectAccess(projectId, actorUserId, superAdmin);
        if (stageReadinessService != null) {
            stageReadinessService.requireSatisfied(
                    projectId,
                    StageIds.REPORT,
                    List.of(StagePrerequisiteKeys.INCLUDED_FINDINGS),
                    actorUserId,
                    superAdmin
            );
        }
        SourceRevisionView sourceRevision = resolveSourceRevision(projectId, request == null ? null : request.sourceRevisionId());
        UUID reportId = UUID.randomUUID();
        Map<String, Object> input = new LinkedHashMap<>();
        input.put("projectId", projectId);
        input.put("sourceRevisionId", sourceRevision.id());
        input.put("reportId", reportId);
        TaskResponse task = taskService.create(new TaskCreateCommand(
                projectId,
                RvPortTaskTypes.REPORT_GENERATE,
                input,
                actorUserId,
                null,
                "迁移评估报告任务已创建"
        ));
        reportRepository.createEvaluation(
                reportId,
                projectId,
                sourceRevision.id(),
                task.id(),
                title(sourceRevision),
                actorUserId
        );
        return task;
    }

    @Transactional(readOnly = true)
    public PageResponse<ReportResponse> list(UUID projectId, ReportListRequest request, UUID actorUserId, boolean superAdmin) {
        projectAccessService.requireProjectAccess(projectId, actorUserId, superAdmin);
        int page = request.normalizedPage();
        int pageSize = request.normalizedPageSize();
        try {
            long total = reportRepository.count(projectId, request);
            List<ReportResponse> items = reportRepository.list(projectId, request)
                    .stream()
                    .map(this::response)
                    .toList();
            return PageResponse.of(items, page, pageSize, total);
        } catch (IllegalArgumentException ex) {
            throw badRequest("REPORT_QUERY_INVALID", "报告查询参数不正确");
        }
    }

    @Transactional(readOnly = true)
    public DomainLatestResponse<ReportResponse> latest(UUID projectId, UUID sourceRevisionId, UUID actorUserId, boolean superAdmin) {
        projectAccessService.requireProjectAccess(projectId, actorUserId, superAdmin);
        ProjectContextSnapshot context = projectContextService.snapshot(projectId);
        UUID effectiveSourceRevisionId = sourceRevisionId == null ? context.sourceRevisionId() : sourceRevisionId;
        return reportRepository.latestEvaluation(projectId, effectiveSourceRevisionId)
                .map(report -> DomainLatestResponse.current(
                        context,
                        DomainLatestExecutionResponse.from(report.id(), taskRepository.findById(report.taskId()).orElse(null)),
                        response(report)))
                .orElseGet(() -> reportRepository.latestEvaluation(projectId, null)
                        .map(report -> DomainLatestResponse.stale(
                                context,
                                DomainLatestExecutionResponse.from(report.id(), taskRepository.findById(report.taskId()).orElse(null)),
                                response(report)))
                        .orElseGet(() -> DomainLatestResponse.empty(context)));
    }

    @Transactional(readOnly = true)
    public ReportReadinessResponse readiness(UUID projectId, UUID sourceRevisionId, UUID actorUserId, boolean superAdmin) {
        projectAccessService.requireProjectAccess(projectId, actorUserId, superAdmin);
        SourceRevisionView sourceRevision = resolveSourceRevisionForReadiness(projectId, sourceRevisionId);
        if (sourceRevision == null) {
            return new ReportReadinessResponse(
                    false,
                    List.of(ReportReadinessIssueResponse.of("SOURCE_REVISION_REQUIRED", "项目没有可用的 active source revision")),
                    List.of(),
                    null,
                    ReportInputSummaryResponse.empty(),
                    reportRepository.latest(projectId, null).map(this::response).orElse(null),
                    false,
                    ReportUpdateSummaryResponse.missing(0),
                    null,
                    null
            );
        }

        ReportInputSummaryResponse inputSummary = currentInputSummary(projectId, sourceRevision.id());
        List<ReportReadinessIssueResponse> blockers = new ArrayList<>();
        List<ReportReadinessIssueResponse> warnings = new ArrayList<>();
        if (inputSummary.lowCandidate() > 0) {
            warnings.add(ReportReadinessIssueResponse.of("LOW_CANDIDATES_NOT_INCLUDED", "存在低风险候选项未进入报告", inputSummary.lowCandidate()));
        }
        if (inputSummary.excluded() > 0) {
            warnings.add(ReportReadinessIssueResponse.of("EXCLUDED_INPUTS_PRESENT", "存在已撤回的迁移输入", inputSummary.excluded()));
        }

        ReportResponse latestReport = reportRepository.latestSucceeded(projectId, sourceRevision.id())
                .map(this::response)
                .orElse(null);
        LatestComparableReportResponse latestComparable = null;
        ReportComparisonSummaryResponse latestComparison = null;
        if (latestReport != null) {
            ReportView latestView = reportRepository.findById(latestReport.id()).orElse(null);
            if (latestView != null) {
                latestComparable = reportComparisonRepository.latestComparableBase(latestView)
                        .map(LatestComparableReportResponse::from)
                        .orElse(null);
                latestComparison = reportComparisonRepository.latestForTargetReport(latestView.id())
                        .map(ReportComparisonSummaryResponse::from)
                        .orElse(null);
            }
        }
        ReportUpdateSummaryResponse reportDiffSummary = latestView(latestReport)
                .map(report -> reportUpdateSummary(report, migrationInputService.currentConfirmedRefsForSystem(projectId, sourceRevision.id())))
                .orElseGet(() -> ReportUpdateSummaryResponse.missing(inputSummary.confirmed()));

        return new ReportReadinessResponse(
                blockers.isEmpty(),
                blockers,
                warnings,
                ReportSourceRevisionSummaryResponse.from(sourceRevision),
                inputSummary,
                latestReport,
                reportDiffSummary.upToDate(),
                reportDiffSummary,
                latestComparable,
                latestComparison
        );
    }

    @Transactional(readOnly = true)
    public ReportResponse get(UUID reportId, UUID actorUserId, boolean superAdmin) {
        return response(requireAccessibleReport(reportId, actorUserId, superAdmin));
    }

    @Transactional(readOnly = true)
    public PageResponse<ReportInputPreviewResponse> inputPreview(UUID projectId, ReportInputPreviewListRequest request, UUID actorUserId, boolean superAdmin) {
        projectAccessService.requireProjectAccess(projectId, actorUserId, superAdmin);
        SourceRevisionView sourceRevision = resolveSourceRevision(projectId, request.sourceRevisionId());
        int page = request.normalizedPage();
        int pageSize = request.normalizedPageSize();
        try {
            List<MigrationInputRefView> filtered = filterInputPreview(migrationInputService.currentRefsForSystem(projectId, sourceRevision.id()), request);
            long total = filtered.size();
            List<ReportInputPreviewResponse> items = filtered.stream()
                    .skip((long) (page - 1) * pageSize)
                    .limit(pageSize)
                    .map(ReportInputPreviewResponse::from)
                    .toList();
            return PageResponse.of(items, page, pageSize, total);
        } catch (IllegalArgumentException ex) {
            throw badRequest("REPORT_INPUT_PREVIEW_QUERY_INVALID", "报告输入预览查询参数不正确");
        }
    }

    @Transactional(readOnly = true)
    public PageResponse<ReportInputResponse> inputs(UUID reportId, ReportInputListRequest request, UUID actorUserId, boolean superAdmin) {
        ReportView report = requireAccessibleReport(reportId, actorUserId, superAdmin);
        int page = request.normalizedPage();
        int pageSize = request.normalizedPageSize();
        try {
            long total = reportRepository.countInputs(report.id(), request);
            List<ReportInputResponse> items = reportRepository.listInputs(report.id(), request)
                    .stream()
                    .map(ReportInputResponse::from)
                    .toList();
            return PageResponse.of(items, page, pageSize, total);
        } catch (IllegalArgumentException ex) {
            throw badRequest("REPORT_INPUT_QUERY_INVALID", "报告输入查询参数不正确");
        }
    }

    @Transactional(readOnly = true)
    public DownloadableReport download(UUID reportId, String format, UUID actorUserId, boolean superAdmin) {
        ReportView report = requireAccessibleReport(reportId, actorUserId, superAdmin);
        ReportDownloadFormat downloadFormat;
        try {
            downloadFormat = ReportDownloadFormat.parse(format);
        } catch (IllegalArgumentException ex) {
            throw badRequest("REPORT_FORMAT_INVALID", "报告下载格式不正确");
        }
        StoredArtifactView artifact = storedArtifactRepository
                .findByOwner(StoredArtifactOwnerType.MIGRATION_REPORT, report.id(), downloadFormat.artifactType())
                .orElseThrow(() -> notFound("REPORT_ARTIFACT_NOT_FOUND", "报告制品不存在"));
        StoredArtifactResource resource = storedArtifactService.download(artifact.id());
        return new DownloadableReport(
                resource.resource(),
                "migration-report-%s.%s".formatted(report.id(), downloadFormat.extension()),
                resource.artifact().contentType()
        );
    }

    private ReportView requireAccessibleReport(UUID reportId, UUID actorUserId, boolean superAdmin) {
        ReportView report = reportRepository.findById(reportId)
                .orElseThrow(() -> notFound("REPORT_NOT_FOUND", "报告不存在"));
        projectAccessService.requireProjectAccess(report.projectId(), actorUserId, superAdmin);
        return report;
    }

    private ReportResponse response(ReportView report) {
        List<ReportArtifactSummaryResponse> artifacts = storedArtifactRepository
                .listByOwner(StoredArtifactOwnerType.MIGRATION_REPORT, report.id())
                .stream()
                .filter(artifact -> "MIGRATION_REPORT_HTML".equals(artifact.artifactType())
                        || "MIGRATION_REPORT_JSON".equals(artifact.artifactType()))
                .map(ReportArtifactSummaryResponse::from)
                .toList();
        LatestComparableReportResponse latestComparable = reportComparisonRepository.latestComparableBase(report)
                .map(LatestComparableReportResponse::from)
                .orElse(null);
        ReportComparisonSummaryResponse latestComparison = reportComparisonRepository.latestForTargetReport(report.id())
                .map(ReportComparisonSummaryResponse::from)
                .orElse(null);
        ReportInputSummaryResponse currentSummary = currentInputSummary(report.projectId(), report.sourceRevisionId());
        ReportUpdateSummaryResponse reportDiffSummary = reportUpdateSummary(report, migrationInputService.currentConfirmedRefsForSystem(report.projectId(), report.sourceRevisionId()));
        return ReportResponse.from(report, artifacts, latestComparable, latestComparison, currentSummary, reportDiffSummary);
    }

    private java.util.Optional<ReportView> latestView(ReportResponse response) {
        if (response == null) {
            return java.util.Optional.empty();
        }
        return reportRepository.findById(response.id());
    }

    private ReportUpdateSummaryResponse reportUpdateSummary(ReportView report, List<MigrationInputRefView> currentRefs) {
        if (report == null) {
            return ReportUpdateSummaryResponse.missing(currentRefs == null ? 0 : currentRefs.size());
        }
        List<ReportInputView> allReportInputs = reportRepository.listAllInputs(report.id());
        List<ReportInputView> reportInputs = (allReportInputs == null ? List.<ReportInputView>of() : allReportInputs).stream()
                .filter(input -> input.inputType() == ReportInputType.MIGRATION_INPUT_REF)
                .toList();
        Map<UUID, MigrationInputRefView> currentById = new HashMap<>();
        for (MigrationInputRefView ref : currentRefs == null ? List.<MigrationInputRefView>of() : currentRefs) {
            currentById.put(ref.id(), ref);
        }
        Map<UUID, ReportInputView> reportByInputId = new HashMap<>();
        for (ReportInputView input : reportInputs) {
            reportByInputId.put(input.inputId(), input);
        }

        List<ReportUpdateSummaryResponse.Item> added = new ArrayList<>();
        List<ReportUpdateSummaryResponse.Item> removed = new ArrayList<>();
        List<ReportUpdateSummaryResponse.Item> changed = new ArrayList<>();

        for (MigrationInputRefView ref : currentById.values()) {
            ReportInputView input = reportByInputId.get(ref.id());
            if (input == null) {
                added.add(item(ref));
            } else if (visibleFieldsChanged(ref, input.inputSnapshot())) {
                changed.add(item(ref));
            }
        }
        for (ReportInputView input : reportInputs) {
            if (!currentById.containsKey(input.inputId())) {
                removed.add(item(input));
            }
        }

        return new ReportUpdateSummaryResponse(
                false,
                added.size(),
                removed.size(),
                changed.size(),
                currentById.size(),
                reportInputs.size(),
                sample(added),
                sample(removed),
                sample(changed)
        );
    }

    private boolean visibleFieldsChanged(MigrationInputRefView ref, Map<String, Object> snapshot) {
        if (snapshot == null) {
            return true;
        }
        return !Objects.equals(ref.issueTitle(), text(snapshot.get("issueTitle")))
                || !Objects.equals(ref.detectedLevel(), text(snapshot.get("detectedLevel")))
                || !Objects.equals(ref.locationLabel(), text(snapshot.get("locationLabel")))
                || !Objects.equals(ref.recommendationSummary(), text(snapshot.get("recommendationSummary")))
                || !Objects.equals(ref.status().name(), text(snapshot.get("status")))
                || !Objects.equals(ref.note(), text(snapshot.get("note")));
    }

    private ReportUpdateSummaryResponse.Item item(MigrationInputRefView ref) {
        return new ReportUpdateSummaryResponse.Item(
                ref.id(),
                ref.issueTitle(),
                ref.sourceType().name(),
                ref.detectedLevel(),
                ref.locationLabel()
        );
    }

    private ReportUpdateSummaryResponse.Item item(ReportInputView input) {
        Map<String, Object> snapshot = input.inputSnapshot() == null ? Map.of() : input.inputSnapshot();
        return new ReportUpdateSummaryResponse.Item(
                input.inputId(),
                text(snapshot.get("issueTitle")),
                text(snapshot.get("sourceType")),
                text(snapshot.get("detectedLevel")),
                text(snapshot.get("locationLabel"))
        );
    }

    private List<ReportUpdateSummaryResponse.Item> sample(List<ReportUpdateSummaryResponse.Item> items) {
        return items.stream().limit(5).toList();
    }

    private String text(Object value) {
        return value == null ? null : String.valueOf(value);
    }

    private ReportInputSummaryResponse currentInputSummary(UUID projectId, UUID sourceRevisionId) {
        Map<String, Long> byStatus = new LinkedHashMap<>();
        Map<String, Long> bySourceType = new LinkedHashMap<>();
        Map<String, Long> byRiskLevel = new LinkedHashMap<>();
        long total = 0;
        long lowCandidate = 0;
        for (MigrationInputRefView ref : migrationInputService.currentRefsForSystem(projectId, sourceRevisionId)) {
            String status = ref.status().name();
            String sourceType = ref.sourceType().name();
            String riskLevel = MigrationInputRiskPolicy.normalizeRiskToken(ref.detectedLevel());
            long count = 1;
            total += count;
            byStatus.merge(status, count, Long::sum);
            bySourceType.merge(sourceType, count, Long::sum);
            byRiskLevel.merge(riskLevel, count, Long::sum);
            if (MigrationInputStatus.CANDIDATE.name().equals(status) && "LOW".equals(riskLevel)) {
                lowCandidate += count;
            }
        }
        return new ReportInputSummaryResponse(
                total,
                byStatus.getOrDefault(MigrationInputStatus.CONFIRMED.name(), 0L),
                byStatus.getOrDefault(MigrationInputStatus.CANDIDATE.name(), 0L),
                byStatus.getOrDefault(MigrationInputStatus.EXCLUDED.name(), 0L),
                lowCandidate,
                Map.copyOf(byStatus),
                Map.copyOf(bySourceType),
                Map.copyOf(byRiskLevel)
        );
    }

    private List<MigrationInputRefView> filterInputPreview(List<MigrationInputRefView> refs, ReportInputPreviewListRequest request) {
        Comparator<MigrationInputRefView> comparator = inputPreviewComparator(request);
        return refs.stream()
                .filter(ref -> request.sourceType() == null || ref.sourceType() == request.sourceType())
                .filter(ref -> request.status() == null || ref.status() == request.status())
                .filter(ref -> matchesRisk(ref, request.riskLevel()))
                .filter(ref -> matchesKeyword(ref, request.keyword()))
                .sorted(comparator)
                .toList();
    }

    private boolean matchesRisk(MigrationInputRefView ref, String riskLevel) {
        if (riskLevel == null || riskLevel.isBlank()) {
            return true;
        }
        if (!MigrationInputRiskPolicy.isKnownRiskToken(riskLevel)) {
            throw new IllegalArgumentException("Unsupported report input preview risk level: " + riskLevel);
        }
        return MigrationInputRiskPolicy.normalizeRiskToken(ref.detectedLevel())
                .equals(MigrationInputRiskPolicy.normalizeRiskToken(riskLevel));
    }

    private boolean matchesKeyword(MigrationInputRefView ref, String keyword) {
        if (keyword == null || keyword.isBlank()) {
            return true;
        }
        String text = keyword.trim().toLowerCase(Locale.ROOT);
        return contains(ref.issueTitle(), text)
                || contains(ref.locationLabel(), text)
                || contains(ref.recommendationSummary(), text)
                || contains(ref.note(), text);
    }

    private boolean contains(String value, String keyword) {
        return value != null && value.toLowerCase(Locale.ROOT).contains(keyword);
    }

    private Comparator<MigrationInputRefView> inputPreviewComparator(ReportInputPreviewListRequest request) {
        String sortBy = request.sortBy() == null ? "" : request.sortBy().trim();
        boolean desc = sortBy.isBlank() || "desc".equalsIgnoreCase(request.sortDirection());
        Comparator<MigrationInputRefView> comparator = switch (sortBy) {
            case "createdAt" -> Comparator.comparing(MigrationInputRefView::createdAt, Comparator.nullsLast(Comparator.naturalOrder()));
            case "updatedAt", "" -> Comparator.comparing(MigrationInputRefView::updatedAt, Comparator.nullsLast(Comparator.naturalOrder()))
                    .thenComparing(MigrationInputRefView::createdAt, Comparator.nullsLast(Comparator.naturalOrder()));
            case "sourceType" -> Comparator.comparing(ref -> ref.sourceType().name(), Comparator.nullsLast(String::compareTo));
            case "detectedLevel" -> Comparator.comparing(MigrationInputRefView::detectedLevel, Comparator.nullsLast(String::compareTo));
            case "status" -> Comparator.comparing(ref -> ref.status().name(), Comparator.nullsLast(String::compareTo));
            case "issueTitle" -> Comparator.comparing(MigrationInputRefView::issueTitle, Comparator.nullsLast(String::compareToIgnoreCase));
            case "locationLabel" -> Comparator.comparing(MigrationInputRefView::locationLabel, Comparator.nullsLast(String::compareToIgnoreCase));
            default -> throw new IllegalArgumentException("Unsupported report input preview sort field: " + request.sortBy());
        };
        comparator = desc ? comparator.reversed() : comparator;
        return comparator.thenComparing(MigrationInputRefView::id);
    }

    private SourceRevisionView resolveSourceRevision(UUID projectId, UUID sourceRevisionId) {
        SourceRevisionView revision = sourceRevisionId == null
                ? sourceRepository.findActive(projectId).orElseThrow(() -> badRequest("SOURCE_REVISION_ACTIVE_NOT_FOUND", "项目没有可用的 active source revision"))
                : sourceRepository.findById(sourceRevisionId).orElseThrow(() -> notFound("SOURCE_REVISION_NOT_FOUND", "源码版本不存在"));
        if (!Objects.equals(revision.projectId(), projectId)) {
            throw notFound("SOURCE_REVISION_NOT_FOUND", "源码版本不存在");
        }
        return revision;
    }

    private SourceRevisionView resolveSourceRevisionForReadiness(UUID projectId, UUID sourceRevisionId) {
        if (sourceRevisionId == null) {
            return sourceRepository.findActive(projectId).orElse(null);
        }
        SourceRevisionView revision = sourceRepository.findById(sourceRevisionId)
                .orElseThrow(() -> notFound("SOURCE_REVISION_NOT_FOUND", "源码版本不存在"));
        if (!Objects.equals(revision.projectId(), projectId)) {
            throw notFound("SOURCE_REVISION_NOT_FOUND", "源码版本不存在");
        }
        return revision;
    }

    private String title(SourceRevisionView revision) {
        String label = revision.versionLabel() == null || revision.versionLabel().isBlank() ? revision.id().toString() : revision.versionLabel();
        return "迁移评估报告 - " + label;
    }

    private ApiException notFound(String code, String message) {
        return new ApiException(HttpStatus.NOT_FOUND, code, message);
    }

    private ApiException badRequest(String code, String message) {
        return new ApiException(HttpStatus.BAD_REQUEST, code, message);
    }

    public record DownloadableReport(Resource resource, String filename, String contentType) {
    }
}
