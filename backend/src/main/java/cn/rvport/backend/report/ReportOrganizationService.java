package cn.rvport.backend.report;

import cn.rvport.backend.artifact.StoredArtifactResource;
import cn.rvport.backend.artifact.StoredArtifactService;
import cn.rvport.backend.common.error.ApiException;
import cn.rvport.backend.common.web.PageResponse;
import cn.rvport.backend.project.ProjectAccessService;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.function.Function;
import java.util.stream.Collectors;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ReportOrganizationService {

    private static final int CONTEXT_RADIUS = 20;
    private static final int DEFAULT_MAX_CONTEXT_LINES = 500;
    private static final List<String> RISK_ORDER = List.of("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO", "COMMENT");

    private final ReportRepository reportRepository;
    private final ReportOrganizationRepository organizationRepository;
    private final ProjectAccessService projectAccessService;
    private final StoredArtifactService storedArtifactService;

    public ReportOrganizationService(
            ReportRepository reportRepository,
            ReportOrganizationRepository organizationRepository,
            ProjectAccessService projectAccessService,
            StoredArtifactService storedArtifactService
    ) {
        this.reportRepository = reportRepository;
        this.organizationRepository = organizationRepository;
        this.projectAccessService = projectAccessService;
        this.storedArtifactService = storedArtifactService;
    }

    @Transactional(readOnly = true)
    public PageResponse<ReportCodeModuleResponse> modules(
            UUID reportId, ReportOrganizationListRequest request, UUID actorUserId, boolean superAdmin
    ) {
        requireAccessibleReport(reportId, actorUserId, superAdmin);
        List<ReportOrganizedInput> inputs = filteredInputs(reportId, request, null, null, null);
        List<ReportCodeModuleResponse> values = inputs.stream()
                .collect(Collectors.groupingBy(input -> defaultText(input.moduleKey(), "unlocated"), LinkedHashMap::new, Collectors.toList()))
                .values().stream().map(this::module).sorted(moduleComparator(request)).toList();
        return page(values, request);
    }

    @Transactional(readOnly = true)
    public PageResponse<ReportCodeFileResponse> files(
            UUID reportId, String moduleKey, ReportOrganizationListRequest request, UUID actorUserId, boolean superAdmin
    ) {
        requireAccessibleReport(reportId, actorUserId, superAdmin);
        requireText(moduleKey, "REPORT_MODULE_KEY_REQUIRED", "模块标识不能为空");
        List<ReportCodeFileResponse> values = filteredInputs(reportId, request, moduleKey, null, null).stream()
                .collect(Collectors.groupingBy(input -> defaultText(input.fileKey(), "unlocated"), LinkedHashMap::new, Collectors.toList()))
                .values().stream().map(this::file).sorted(fileComparator(request)).toList();
        return page(values, request);
    }

    @Transactional(readOnly = true)
    public PageResponse<ReportFindingTypeResponse> findingTypes(
            UUID reportId, String moduleKey, String fileKey, ReportOrganizationListRequest request,
            UUID actorUserId, boolean superAdmin
    ) {
        requireAccessibleReport(reportId, actorUserId, superAdmin);
        requireText(moduleKey, "REPORT_MODULE_KEY_REQUIRED", "模块标识不能为空");
        requireText(fileKey, "REPORT_FILE_KEY_REQUIRED", "文件标识不能为空");
        List<ReportFindingTypeResponse> values = filteredInputs(reportId, request, moduleKey, fileKey, null).stream()
                .collect(Collectors.groupingBy(input -> defaultText(input.findingType(), "UNCLASSIFIED"), LinkedHashMap::new, Collectors.toList()))
                .values().stream().map(this::findingType).sorted(typeComparator(request)).toList();
        return page(values, request);
    }

    @Transactional(readOnly = true)
    public PageResponse<ReportCodeFindingResponse> findings(
            UUID reportId, String moduleKey, String fileKey, String findingType,
            ReportOrganizationListRequest request, UUID actorUserId, boolean superAdmin
    ) {
        requireAccessibleReport(reportId, actorUserId, superAdmin);
        requireText(moduleKey, "REPORT_MODULE_KEY_REQUIRED", "模块标识不能为空");
        requireText(fileKey, "REPORT_FILE_KEY_REQUIRED", "文件标识不能为空");
        List<ReportCodeFindingResponse> values = filteredInputs(reportId, request, moduleKey, fileKey, findingType).stream()
                .sorted(findingComparator(request)).map(this::finding).toList();
        return page(values, request);
    }

    @Transactional(readOnly = true)
    public ReportFileContextResponse context(
            UUID reportId, String fileKey, ReportFileContextRequest request, UUID actorUserId, boolean superAdmin
    ) {
        request = request == null ? new ReportFileContextRequest(null, null) : request;
        requireAccessibleReport(reportId, actorUserId, superAdmin);
        requireText(fileKey, "REPORT_FILE_KEY_REQUIRED", "文件标识不能为空");
        ReportFileContextView context = organizationRepository.findFileContext(reportId, fileKey)
                .orElseThrow(() -> notFound("REPORT_FILE_CONTEXT_NOT_FOUND", "报告文件上下文不存在"));
        List<ReportCodeFindingResponse> findings = organizationRepository.listCodeInputs(reportId).stream()
                .filter(input -> Objects.equals(input.fileKey(), fileKey))
                .sorted(defaultFindingComparator())
                .map(this::finding)
                .toList();
        if (!context.contextAvailable() || context.artifactId() == null) {
            return unavailableContext(context, findings, context.unavailableReason());
        }
        try {
            StoredArtifactResource artifact = storedArtifactService.download(context.artifactId());
            String content = new String(artifact.resource().getInputStream().readAllBytes(), StandardCharsets.UTF_8);
            List<String> sourceLines = List.of(content.split("\\R", -1));
            List<ReportFileContextResponse.Block> blocks = request.fromLine() == null
                    ? defaultBlocks(sourceLines, findings, request.normalizedLines())
                    : List.of(codeBlock(sourceLines, findings, request.fromLine(),
                            Math.min(sourceLines.size(), request.fromLine() + request.normalizedLines() - 1)));
            return new ReportFileContextResponse(reportId, context.sourceRevisionId(), fileKey, context.relativePath(),
                    context.contentHash(), context.totalLines(), true, null, findings, blocks);
        } catch (IOException | RuntimeException ex) {
            return unavailableContext(context, findings, "CONTEXT_ARTIFACT_UNAVAILABLE");
        }
    }

    public boolean organizationAvailable(UUID reportId) {
        return organizationRepository.organizationAvailable(reportId);
    }

    private List<ReportOrganizedInput> filteredInputs(
            UUID reportId, ReportOrganizationListRequest request, String moduleKey, String fileKey, String findingType
    ) {
        return organizationRepository.listCodeInputs(reportId).stream()
                .filter(input -> moduleKey == null || Objects.equals(input.moduleKey(), moduleKey))
                .filter(input -> fileKey == null || Objects.equals(input.fileKey(), fileKey))
                .filter(input -> findingType == null || findingType.isBlank() || Objects.equals(input.findingType(), findingType))
                .filter(input -> request.riskLevel() == null || request.riskLevel().isBlank()
                        || Objects.equals(input.riskLevel(), request.riskLevel().trim().toUpperCase(Locale.ROOT)))
                .filter(input -> matchesKeyword(input, request.keyword()))
                .toList();
    }

    private boolean matchesKeyword(ReportOrganizedInput input, String keyword) {
        if (keyword == null || keyword.isBlank()) {
            return true;
        }
        String value = keyword.trim().toLowerCase(Locale.ROOT);
        return contains(input.moduleName(), value) || contains(input.relativePath(), value)
                || contains(input.findingType(), value) || contains(text(input.snapshot().get("issueTitle")), value)
                || contains(input.symbol(), value);
    }

    private ReportCodeModuleResponse module(List<ReportOrganizedInput> inputs) {
        ReportOrganizedInput first = inputs.getFirst();
        return new ReportCodeModuleResponse(first.moduleKey(), first.moduleName(), first.moduleBasis(), first.moduleConfidence(),
                first.relatedModuleKeys(), distinct(inputs, ReportOrganizedInput::fileKey), inputs.size(),
                distinct(inputs, ReportOrganizedInput::findingType), highestRisk(inputs), counts(inputs, ReportOrganizedInput::riskLevel),
                counts(inputs, ReportOrganizedInput::findingType));
    }

    private ReportCodeFileResponse file(List<ReportOrganizedInput> inputs) {
        ReportOrganizedInput first = inputs.getFirst();
        return new ReportCodeFileResponse(first.fileKey(), first.relativePath(), first.sourceContentHash(),
                first.sourceContentHash() != null, inputs.size(), distinct(inputs, ReportOrganizedInput::findingType),
                highestRisk(inputs), counts(inputs, ReportOrganizedInput::riskLevel), counts(inputs, ReportOrganizedInput::findingType));
    }

    private ReportFindingTypeResponse findingType(List<ReportOrganizedInput> inputs) {
        return new ReportFindingTypeResponse(defaultText(inputs.getFirst().findingType(), "UNCLASSIFIED"), inputs.size(), highestRisk(inputs),
                inputs.stream().map(ReportOrganizedInput::lineStart).filter(Objects::nonNull).min(Integer::compareTo).orElse(null),
                inputs.stream().map(ReportOrganizedInput::lineEnd).filter(Objects::nonNull).max(Integer::compareTo).orElse(null),
                distinct(inputs, ReportOrganizedInput::symbol));
    }

    private ReportCodeFindingResponse finding(ReportOrganizedInput input) {
        return new ReportCodeFindingResponse(input.inputId(), uuid(input.snapshot().get("sourceRefId")), text(input.snapshot().get("issueTitle")), input.riskLevel(),
                input.findingType(), input.relativePath(), input.lineStart(), input.lineEnd(), input.columnStart(), input.columnEnd(),
                input.symbol(), input.locationAvailable(), text(input.snapshot().get("recommendationSummary")), map(input.snapshot().get("sourceDetail")));
    }

    private List<ReportFileContextResponse.Block> defaultBlocks(
            List<String> sourceLines, List<ReportCodeFindingResponse> findings, int requestedLimit
    ) {
        List<int[]> windows = findings.stream()
                .filter(finding -> finding.lineStart() != null)
                .map(finding -> new int[]{Math.max(1, finding.lineStart() - CONTEXT_RADIUS),
                        Math.min(sourceLines.size(), defaultEnd(finding) + CONTEXT_RADIUS)})
                .sorted(Comparator.comparingInt(window -> window[0]))
                .toList();
        if (windows.isEmpty()) {
            return List.of();
        }
        int first = windows.getFirst()[0];
        int last = windows.getLast()[1];
        int maxLines = requestedLimit <= 0 ? DEFAULT_MAX_CONTEXT_LINES : requestedLimit;
        if (last - first + 1 <= maxLines) {
            return List.of(codeBlock(sourceLines, findings, first, last));
        }
        List<int[]> merged = new ArrayList<>();
        for (int[] window : windows) {
            if (merged.isEmpty() || window[0] > merged.getLast()[1] + 1) {
                merged.add(new int[]{window[0], window[1]});
            } else {
                merged.getLast()[1] = Math.max(merged.getLast()[1], window[1]);
            }
        }
        List<ReportFileContextResponse.Block> blocks = new ArrayList<>();
        for (int index = 0; index < merged.size(); index++) {
            int[] window = merged.get(index);
            blocks.add(codeBlock(sourceLines, findings, window[0], window[1]));
            if (index + 1 < merged.size()) {
                int start = window[1] + 1;
                int end = merged.get(index + 1)[0] - 1;
                blocks.add(new ReportFileContextResponse.Block("OMITTED", start, end, end - start + 1,
                        "DISTANT_FINDING_GAP", true, List.of()));
            }
        }
        return List.copyOf(blocks);
    }

    private ReportFileContextResponse.Block codeBlock(
            List<String> sourceLines, List<ReportCodeFindingResponse> findings, int requestedStart, int requestedEnd
    ) {
        int start = Math.max(1, requestedStart);
        int end = Math.min(sourceLines.size(), Math.max(start - 1, requestedEnd));
        List<ReportFileContextResponse.Line> lines = new ArrayList<>();
        for (int lineNumber = start; lineNumber <= end; lineNumber++) {
            int currentLine = lineNumber;
            List<ReportFileContextResponse.Highlight> highlights = findings.stream()
                    .filter(finding -> finding.lineStart() != null && currentLine >= finding.lineStart() && currentLine <= defaultEnd(finding))
                    .map(finding -> new ReportFileContextResponse.Highlight(finding.id(), finding.columnStart(), finding.columnEnd()))
                    .toList();
            lines.add(new ReportFileContextResponse.Line(lineNumber, sourceLines.get(lineNumber - 1), highlights));
        }
        return new ReportFileContextResponse.Block("CODE", start, end, Math.max(0, end - start + 1), null, false, List.copyOf(lines));
    }

    private int defaultEnd(ReportCodeFindingResponse finding) {
        return finding.lineEnd() == null ? finding.lineStart() : Math.max(finding.lineStart(), finding.lineEnd());
    }

    private ReportFileContextResponse unavailableContext(
            ReportFileContextView context, List<ReportCodeFindingResponse> findings, String reason
    ) {
        return new ReportFileContextResponse(context.reportId(), context.sourceRevisionId(), context.fileKey(), context.relativePath(),
                context.contentHash(), context.totalLines(), false, defaultText(reason, "CONTEXT_UNAVAILABLE"), findings, List.of());
    }

    private Comparator<ReportCodeModuleResponse> moduleComparator(ReportOrganizationListRequest request) {
        Comparator<ReportCodeModuleResponse> comparator = switch (sortBy(request, "moduleName")) {
            case "moduleName" -> Comparator.comparing(ReportCodeModuleResponse::moduleName, Comparator.nullsLast(String.CASE_INSENSITIVE_ORDER));
            case "fileCount" -> Comparator.comparingLong(ReportCodeModuleResponse::fileCount);
            case "findingCount" -> Comparator.comparingLong(ReportCodeModuleResponse::findingCount);
            case "highestRisk" -> Comparator.comparingInt(value -> riskRank(value.highestRisk()));
            default -> throw invalidQuery();
        };
        return direction(comparator, request).thenComparing(ReportCodeModuleResponse::moduleKey);
    }

    private Comparator<ReportCodeFileResponse> fileComparator(ReportOrganizationListRequest request) {
        Comparator<ReportCodeFileResponse> comparator = switch (sortBy(request, "relativePath")) {
            case "relativePath" -> Comparator.comparing(ReportCodeFileResponse::relativePath, Comparator.nullsLast(String.CASE_INSENSITIVE_ORDER));
            case "findingCount" -> Comparator.comparingLong(ReportCodeFileResponse::findingCount);
            case "highestRisk" -> Comparator.comparingInt(value -> riskRank(value.highestRisk()));
            default -> throw invalidQuery();
        };
        return direction(comparator, request).thenComparing(ReportCodeFileResponse::fileKey);
    }

    private Comparator<ReportFindingTypeResponse> typeComparator(ReportOrganizationListRequest request) {
        Comparator<ReportFindingTypeResponse> comparator = switch (sortBy(request, "findingType")) {
            case "findingType" -> Comparator.comparing(ReportFindingTypeResponse::findingType, Comparator.nullsLast(String.CASE_INSENSITIVE_ORDER));
            case "findingCount" -> Comparator.comparingLong(ReportFindingTypeResponse::findingCount);
            case "highestRisk" -> Comparator.comparingInt(value -> riskRank(value.highestRisk()));
            case "firstLine" -> Comparator.comparing(ReportFindingTypeResponse::firstLine, Comparator.nullsLast(Integer::compareTo));
            default -> throw invalidQuery();
        };
        return direction(comparator, request).thenComparing(ReportFindingTypeResponse::findingType);
    }

    private Comparator<ReportOrganizedInput> findingComparator(ReportOrganizationListRequest request) {
        String sortBy = sortBy(request, "lineStart");
        if ("lineStart".equals(sortBy) && (request.sortDirection() == null || !"desc".equalsIgnoreCase(request.sortDirection()))) {
            return defaultFindingComparator();
        }
        Comparator<ReportOrganizedInput> comparator = switch (sortBy) {
            case "lineStart" -> Comparator.comparing(ReportOrganizedInput::lineStart, Comparator.nullsLast(Integer::compareTo));
            case "riskLevel" -> Comparator.comparingInt(value -> riskRank(value.riskLevel()));
            case "issueTitle" -> Comparator.comparing(value -> text(value.snapshot().get("issueTitle")), Comparator.nullsLast(String.CASE_INSENSITIVE_ORDER));
            default -> throw invalidQuery();
        };
        return direction(comparator, request).thenComparing(ReportOrganizedInput::id);
    }

    private Comparator<ReportOrganizedInput> defaultFindingComparator() {
        return Comparator.comparing(ReportOrganizedInput::lineStart, Comparator.nullsLast(Integer::compareTo))
                .thenComparing(ReportOrganizedInput::lineEnd, Comparator.nullsLast(Integer::compareTo))
                .thenComparing(ReportOrganizedInput::id);
    }

    private <T> Comparator<T> direction(Comparator<T> comparator, ReportOrganizationListRequest request) {
        if (request.sortDirection() == null || request.sortDirection().isBlank() || "asc".equalsIgnoreCase(request.sortDirection())) {
            return comparator;
        }
        if ("desc".equalsIgnoreCase(request.sortDirection())) {
            return comparator.reversed();
        }
        throw invalidQuery();
    }

    private String sortBy(ReportOrganizationListRequest request, String fallback) {
        return request.sortBy() == null || request.sortBy().isBlank() ? fallback : request.sortBy().trim();
    }

    private <T> PageResponse<T> page(List<T> values, ReportOrganizationListRequest request) {
        int page = request.normalizedPage();
        int pageSize = request.normalizedPageSize();
        long offset = (long) (page - 1) * pageSize;
        List<T> items = offset >= values.size() ? List.of() : values.stream().skip(offset).limit(pageSize).toList();
        return PageResponse.of(items, page, pageSize, values.size());
    }

    private Map<String, Long> counts(List<ReportOrganizedInput> inputs, Function<ReportOrganizedInput, String> classifier) {
        return inputs.stream().map(classifier).map(value -> defaultText(value, "UNKNOWN"))
                .collect(Collectors.groupingBy(Function.identity(), LinkedHashMap::new, Collectors.counting()));
    }

    private long distinct(List<ReportOrganizedInput> inputs, Function<ReportOrganizedInput, String> classifier) {
        return inputs.stream().map(classifier).filter(value -> value != null && !value.isBlank()).distinct().count();
    }

    private String highestRisk(List<ReportOrganizedInput> inputs) {
        return inputs.stream().map(ReportOrganizedInput::riskLevel).map(value -> defaultText(value, "INFO"))
                .min(Comparator.comparingInt(this::riskRank)).orElse("INFO");
    }

    private int riskRank(String value) {
        int index = RISK_ORDER.indexOf(defaultText(value, "INFO").toUpperCase(Locale.ROOT));
        return index < 0 ? RISK_ORDER.indexOf("INFO") : index;
    }

    private ReportView requireAccessibleReport(UUID reportId, UUID actorUserId, boolean superAdmin) {
        ReportView report = reportRepository.findById(reportId)
                .orElseThrow(() -> notFound("REPORT_NOT_FOUND", "报告不存在"));
        projectAccessService.requireProjectAccess(report.projectId(), actorUserId, superAdmin);
        return report;
    }

    private void requireText(String value, String code, String message) {
        if (value == null || value.isBlank()) {
            throw new ApiException(HttpStatus.BAD_REQUEST, code, message);
        }
    }

    private boolean contains(String value, String keyword) {
        return value != null && value.toLowerCase(Locale.ROOT).contains(keyword);
    }

    private String text(Object value) {
        return value == null ? null : String.valueOf(value);
    }

    private Map<String, Object> map(Object value) {
        if (!(value instanceof Map<?, ?> source)) {
            return Map.of();
        }
        Map<String, Object> result = new LinkedHashMap<>();
        source.forEach((key, item) -> result.put(String.valueOf(key), item));
        return result;
    }

    private UUID uuid(Object value) {
        if (value instanceof UUID id) {
            return id;
        }
        try {
            return value == null ? null : UUID.fromString(String.valueOf(value));
        } catch (IllegalArgumentException ex) {
            return null;
        }
    }

    private String defaultText(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }

    private ApiException invalidQuery() {
        return new ApiException(HttpStatus.BAD_REQUEST, "REPORT_ORGANIZATION_QUERY_INVALID", "报告组织查询参数不正确");
    }

    private ApiException notFound(String code, String message) {
        return new ApiException(HttpStatus.NOT_FOUND, code, message);
    }
}
