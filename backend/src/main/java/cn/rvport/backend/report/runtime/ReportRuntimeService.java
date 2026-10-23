package cn.rvport.backend.report.runtime;

import cn.rvport.backend.artifact.StoredArtifactCreateCommand;
import cn.rvport.backend.artifact.StoredArtifactOwnerType;
import cn.rvport.backend.artifact.StoredArtifactRepository;
import cn.rvport.backend.artifact.StoredArtifactService;
import cn.rvport.backend.artifact.StoredArtifactView;
import cn.rvport.backend.archive.ArchiveCandidateRegistrar;
import cn.rvport.backend.migration.MigrationInputRefView;
import cn.rvport.backend.migration.MigrationInputService;
import cn.rvport.backend.migration.MigrationInputSourceResolver;
import cn.rvport.backend.report.ReportDownloadFormat;
import cn.rvport.backend.report.ReportGenerateInput;
import cn.rvport.backend.report.ReportInputProjection;
import cn.rvport.backend.report.ReportRepository;
import cn.rvport.backend.report.ReportView;
import cn.rvport.backend.source.SourceRepository;
import cn.rvport.backend.source.SourceRevisionView;
import cn.rvport.backend.task.TaskErrorCode;
import cn.rvport.backend.task.TaskExecutionException;
import cn.rvport.backend.task.TaskLogType;
import cn.rvport.backend.task.TaskStatus;
import cn.rvport.backend.worker.TaskCancelledException;
import cn.rvport.backend.worker.TaskExecutionContext;
import cn.rvport.backend.worker.TaskAttemptLostException;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Service
public class ReportRuntimeService {

    private static final Logger log = LoggerFactory.getLogger(ReportRuntimeService.class);
    private static final String SCHEMA_VERSION = "migration-report/v2";
    private static final List<String> RISK_ORDER = List.of("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO", "COMMENT");
    private static final int PRIORITY_LIMIT = 10;
    private static final String LOGO_SVG = """
            <svg width="121" height="33" viewBox="0 0 121 33" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="RvPort">
            <path d="M42.5355 7.28699H38.6004C38.1085 7.28699 37.7079 7.68759 37.7079 8.17948V15.4259C37.7079 17.3529 36.0953 18.9046 34.143 18.8032C32.3124 18.7068 30.9432 17.0638 30.9432 15.2332V8.17948C30.9432 7.68759 30.5426 7.28699 30.0507 7.28699H26.1156C25.6238 7.28699 25.2231 7.68759 25.2231 8.17948V15.1267C25.2231 19.721 28.5041 23.8133 33.0527 24.4472C34.5487 24.6551 35.9787 24.4878 37.2769 24.0415C37.4189 23.9959 37.5558 24.1226 37.5051 24.2646C36.9574 25.7707 35.5223 26.8508 33.8286 26.8508H31.141C30.6491 26.8508 30.2485 27.2514 30.2485 27.7433V31.6784C30.2485 32.1703 30.6491 32.5709 31.141 32.5709H34.1481C39.2799 32.5709 43.4381 28.4127 43.4381 23.2809V8.17948C43.4381 7.68759 43.0375 7.28699 42.5456 7.28699H42.5355Z" fill="#1F70EA"/>
            <path d="M15.0912 15.1724C18.4077 14.2444 20.8265 11.1612 20.7302 7.52026C20.6186 3.37727 16.8509 0 12.7079 0H0.892493C0.400607 0 0 0.400607 0 0.892493V23.6358C0 24.1277 0.400607 24.5283 0.892493 24.5283H4.82757C5.31946 24.5283 5.72007 24.1277 5.72007 23.6358V15.9077C5.72007 15.6592 5.92291 15.4614 6.16631 15.4614H7.94116C8.20485 15.4614 8.45333 15.5781 8.62574 15.7758L15.791 24.219C15.9634 24.4168 16.2119 24.5334 16.4756 24.5334H22.287C22.4797 24.5334 22.5811 24.3103 22.4543 24.1632L14.9746 15.5273C14.8681 15.4006 14.929 15.2129 15.0862 15.1724H15.0912ZM5.72514 9.28497V6.18153C5.72514 5.93305 5.92798 5.73528 6.17138 5.73528H12.8955C13.9401 5.73528 14.8935 6.48578 15 7.53041C15.1217 8.72716 14.1835 9.73628 13.0121 9.73628H6.17138C5.92291 9.73628 5.72514 9.53344 5.72514 9.29004V9.28497Z" fill="#1F70EA"/>
            <path d="M61.2782 0.00500488C66.7954 0.00500488 70.2691 3.40256 70.2691 8.44819C70.2691 13.4938 66.689 17.0029 61.0196 17.0029H55.7508C55.4719 17.0029 55.2438 17.2311 55.2438 17.51V23.9907C55.2438 24.2696 55.0156 24.4978 54.7367 24.4978H49.7215C49.4425 24.4978 49.2144 24.2696 49.2144 23.9907V1.0192C49.2144 0.461393 49.6707 0.00500488 50.2286 0.00500488H61.2782ZM60.5835 11.9573C62.9212 11.9573 64.3462 10.6034 64.3462 8.51918C64.3462 6.54657 62.9212 5.15712 60.5835 5.15712H55.7559C55.477 5.15712 55.2488 5.38532 55.2488 5.66422V11.4502C55.2488 11.7291 55.477 11.9573 55.7559 11.9573H60.5835Z" fill="#1F70EA"/>
            </svg>
            """;

    private final ReportRepository reportRepository;
    private final MigrationInputService migrationInputService;
    private final MigrationInputSourceResolver sourceResolver;
    private final ReportStatusWriter reportStatusWriter;
    private final StoredArtifactRepository storedArtifactRepository;
    private final StoredArtifactService storedArtifactService;
    private final ArchiveCandidateRegistrar archiveCandidateRegistrar;
    private final ObjectMapper objectMapper;
    private final SourceRepository sourceRepository;
    private final ReportOrganizationProjector organizationProjector;
    private final ReportFileContextSnapshotter contextSnapshotter;

    @Autowired
    public ReportRuntimeService(
            ReportRepository reportRepository,
            MigrationInputService migrationInputService,
            MigrationInputSourceResolver sourceResolver,
            ReportStatusWriter reportStatusWriter,
            StoredArtifactRepository storedArtifactRepository,
            StoredArtifactService storedArtifactService,
            ArchiveCandidateRegistrar archiveCandidateRegistrar,
            ObjectMapper objectMapper,
            SourceRepository sourceRepository,
            ReportOrganizationProjector organizationProjector,
            ReportFileContextSnapshotter contextSnapshotter
    ) {
        this.reportRepository = reportRepository;
        this.migrationInputService = migrationInputService;
        this.sourceResolver = sourceResolver;
        this.reportStatusWriter = reportStatusWriter;
        this.storedArtifactRepository = storedArtifactRepository;
        this.storedArtifactService = storedArtifactService;
        this.archiveCandidateRegistrar = archiveCandidateRegistrar;
        this.objectMapper = objectMapper;
        this.sourceRepository = sourceRepository;
        this.organizationProjector = organizationProjector;
        this.contextSnapshotter = contextSnapshotter;
    }

    ReportRuntimeService(
            ReportRepository reportRepository,
            MigrationInputService migrationInputService,
            MigrationInputSourceResolver sourceResolver,
            ReportStatusWriter reportStatusWriter,
            StoredArtifactRepository storedArtifactRepository,
            StoredArtifactService storedArtifactService,
            ArchiveCandidateRegistrar archiveCandidateRegistrar,
            ObjectMapper objectMapper
    ) {
        this(reportRepository, migrationInputService, sourceResolver, reportStatusWriter, storedArtifactRepository,
                storedArtifactService, archiveCandidateRegistrar, objectMapper, null,
                new ReportOrganizationProjector(), null);
    }

    public void generate(ReportGenerateInput input, TaskExecutionContext context) {
        validate(input, context);
        ReportView report = reportRepository.findById(input.reportId())
                .orElseThrow(() -> new TaskExecutionException(TaskErrorCode.RESOURCE_NOT_FOUND, "报告记录不存在", null));
        String failureStage = "START";
        context.publish(() -> reportStatusWriter.updateStatus(report.id(), TaskStatus.RUNNING, Map.of("phase", "RUNNING")));
        try {
            failureStage = "READ_CONFIRMED_INPUTS";
            context.progress(10, "读取已确认迁移输入");
            List<MigrationInputRefView> refs = migrationInputService.currentConfirmedRefsForSystem(input.projectId(), input.sourceRevisionId());

            failureStage = "WRITE_INPUT_SNAPSHOT";
            context.progress(35, "生成报告输入快照");
            SourceRevisionView revision = sourceRepository == null ? null : sourceRepository.findById(input.sourceRevisionId()).orElse(null);
            Path sourceRoot = revision == null || revision.workingCopyPath() == null
                    ? null : Path.of(revision.workingCopyPath()).toAbsolutePath().normalize();
            List<ReportRepository.ReportInputSnapshot> snapshots = refs.stream()
                    .map(ref -> snapshot(ref, sourceRoot))
                    .toList();
            if (contextSnapshotter != null) {
                Map<String, String> hashes = contextSnapshotter.capture(report, revision, snapshots, context);
                snapshots = snapshots.stream().map(snapshot -> withContentHash(snapshot, hashes)).toList();
            }
            List<ReportRepository.ReportInputSnapshot> readySnapshots = snapshots;
            context.publish(() -> { reportRepository.replaceInputs(report.id(), readySnapshots); return null; });

            failureStage = "RENDER_REPORT";
            context.progress(60, "生成报告内容");
            Map<String, Object> summary = summary(refs, snapshots);
            String riskLevel = overallRisk(refs);
            Map<String, Object> jsonReport = jsonReport(report, input, summary, riskLevel, snapshots);
            byte[] jsonBytes = prettyJson(jsonReport);
            byte[] htmlBytes = htmlReport(report, summary, riskLevel, snapshots).getBytes(StandardCharsets.UTF_8);

            failureStage = "SAVE_ARTIFACTS";
            context.progress(80, "保存报告制品");
            StoredArtifactView jsonArtifact = saveJson(report, jsonReport, jsonBytes, summary, context);
            StoredArtifactView htmlArtifact = saveHtml(report, htmlBytes, summary, context);
            ReportView succeededReport = context.publish(() -> reportStatusWriter.markSucceeded(report.id(), summary, riskLevel));
            try {
                context.publish(() -> {
                archiveCandidateRegistrar.registerMigrationReport(
                        succeededReport == null ? report : succeededReport,
                        summary,
                        List.of(jsonArtifact, htmlArtifact)
                );
                return null;
                });
            } catch (TaskAttemptLostException ex) {
                throw ex;
            } catch (RuntimeException ex) {
                log.warn("Migration report archive candidate registration failed reportId={} taskId={} stage=REGISTER_ARCHIVE_CANDIDATE cause={}: {}",
                        report.id(), report.taskId(), ex.getClass().getName(), sanitize(ex.getMessage()), sanitizedThrowable(ex));
                try {
                    context.log(TaskLogType.STDERR, "迁移评估报告已生成，但归档候选登记失败: " + sanitize(ex.getMessage()));
                } catch (RuntimeException ignored) {
                    // 报告已生成，归档候选失败日志不能反向破坏成功状态。
                }
            }
            context.log(TaskLogType.STDOUT, "迁移评估报告已生成，confirmed 输入数量: " + refs.size());
            context.progress(95, "报告生成完成");
        } catch (TaskAttemptLostException ex) {
            throw ex;
        } catch (TaskCancelledException ex) {
            failReport(context, report, TaskStatus.CANCELLED, failureSummary(null, "任务已取消", failureStage, ex));
            throw ex;
        } catch (TaskExecutionException ex) {
            failReport(context, report, TaskStatus.FAILED, failureSummary(ex.errorCode(), ex.safeMessage(), failureStage, ex.getCause()));
            throw ex;
        } catch (RuntimeException ex) {
            failReport(context, report, TaskStatus.FAILED, failureSummary(TaskErrorCode.HANDLER_FAILED, "报告生成失败", failureStage, ex));
            throw new TaskExecutionException(TaskErrorCode.HANDLER_FAILED, "报告生成失败，阶段: " + failureStage, ex);
        }
    }

    private void validate(ReportGenerateInput input, TaskExecutionContext context) {
        if (input == null || input.projectId() == null || input.sourceRevisionId() == null || input.reportId() == null) {
            throw new TaskExecutionException(TaskErrorCode.INPUT_INVALID, "报告任务输入非法", null);
        }
        if (!Objects.equals(input.projectId(), context.task().projectId())) {
            throw new TaskExecutionException(TaskErrorCode.PROJECT_MISMATCH, "报告任务项目不匹配", null);
        }
    }

    private ReportRepository.ReportInputSnapshot snapshot(MigrationInputRefView ref, Path sourceRoot) {
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
        snapshot.put("status", ref.status().name());
        snapshot.put("note", ref.note());
        snapshot.put("ruleId", ref.ruleId());
        snapshot.put("identityPath", ref.identityPath());
        snapshot.put("identitySymbol", ref.identitySymbol());
        snapshot.put("identityAnchor", ref.identityAnchor());
        snapshot.put("stableFingerprint", ref.stableFingerprint());
        snapshot.put("createdAt", ref.createdAt());
        snapshot.put("updatedAt", ref.updatedAt());
        snapshot.put("sourceDetail", sourceResolver.detail(ref));
        ReportInputProjection projection = organizationProjector.project(ref, snapshot, sourceRoot);
        return new ReportRepository.ReportInputSnapshot(ref, snapshot, projection);
    }

    private ReportRepository.ReportInputSnapshot withContentHash(
            ReportRepository.ReportInputSnapshot snapshot,
            Map<String, String> hashes
    ) {
        ReportInputProjection projection = snapshot.projection();
        if (projection == null || projection.fileKey() == null) {
            return snapshot;
        }
        return new ReportRepository.ReportInputSnapshot(snapshot.ref(), snapshot.snapshot(),
                projection.withSourceContentHash(hashes.get(projection.fileKey())));
    }

    private Map<String, Object> summary(List<MigrationInputRefView> refs, List<ReportRepository.ReportInputSnapshot> snapshots) {
        Map<String, Long> bySourceType = refs.stream()
                .collect(java.util.stream.Collectors.groupingBy(ref -> ref.sourceType().name(), LinkedHashMap::new, java.util.stream.Collectors.counting()));
        Map<String, Long> byDetectedLevel = refs.stream()
                .collect(java.util.stream.Collectors.groupingBy(ref -> defaultText(ref.detectedLevel(), "UNKNOWN"), LinkedHashMap::new, java.util.stream.Collectors.counting()));
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("schemaVersion", SCHEMA_VERSION);
        summary.put("confirmedInputCount", refs.size());
        summary.put("highRiskIssueCount", highRiskIssueCount(refs));
        summary.put("estimatedWorkload", estimatedWorkload(refs));
        summary.put("sourceTypeCounts", bySourceType);
        summary.put("detectedLevelCounts", byDetectedLevel);
        summary.put("dependencyAnalysisInputCount", dependencyRefs(refs).size());
        summary.put("dependencyRiskCounts", dependencyRiskCounts(refs));
        summary.put("dependencyTargetMatchStatusCounts", dependencyTargetMatchStatusCounts(refs));
        summary.put("mainDependencyRisks", dependencySubstitutionNotes(refs));
        summary.put("priorityIssues", priorityIssues(refs));
        summary.put("dependencySubstitutionNotes", dependencySubstitutionNotes(refs));
        summary.put("organizationAvailable", true);
        summary.put("codeFindingCount", snapshots.stream().filter(item -> item.projection() != null && item.projection().moduleKey() != null).count());
        summary.put("codeModuleCount", snapshots.stream().map(ReportRepository.ReportInputSnapshot::projection)
                .filter(Objects::nonNull).map(ReportInputProjection::moduleKey).filter(Objects::nonNull).distinct().count());
        summary.put("codeFileCount", snapshots.stream().map(ReportRepository.ReportInputSnapshot::projection)
                .filter(Objects::nonNull).map(ReportInputProjection::fileKey).filter(Objects::nonNull).distinct().count());
        summary.put("generatedAt", OffsetDateTime.now());
        return summary;
    }

    private String overallRisk(List<MigrationInputRefView> refs) {
        return refs.stream()
                .map(ref -> riskToken(ref.detectedLevel()))
                .min(Comparator.comparingInt(this::riskRank))
                .orElse("INFO");
    }

    private String riskToken(String detectedLevel) {
        String value = defaultText(detectedLevel, "INFO").toUpperCase(Locale.ROOT);
        int slash = value.indexOf('/');
        return slash < 0 ? value : value.substring(0, slash);
    }

    private int riskRank(String risk) {
        int index = RISK_ORDER.indexOf(risk);
        return index < 0 ? RISK_ORDER.indexOf("INFO") : index;
    }

    private Map<String, Object> jsonReport(
            ReportView report,
            ReportGenerateInput input,
            Map<String, Object> summary,
            String riskLevel,
            List<ReportRepository.ReportInputSnapshot> snapshots
    ) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("schemaVersion", SCHEMA_VERSION);
        payload.put("report", Map.of(
                "id", report.id(),
                "projectId", report.projectId(),
                "sourceRevisionId", input.sourceRevisionId(),
                "taskId", report.taskId(),
                "title", report.title(),
                "riskLevel", riskLevel
        ));
        payload.put("summary", summary);
        payload.put("sections", Map.of(
                "majorRisks", summary.get("priorityIssues"),
                "dependencySubstitutionNotes", summary.get("dependencySubstitutionNotes"),
                "estimatedWorkload", summary.get("estimatedWorkload")
        ));
        payload.put("organization", ReportDocumentOrganizer.organize(snapshots));
        payload.put("inputs", snapshots.stream().map(ReportRepository.ReportInputSnapshot::snapshot).toList());
        return payload;
    }

    private byte[] prettyJson(Map<String, Object> value) {
        try {
            return objectMapper.writerWithDefaultPrettyPrinter().writeValueAsBytes(value);
        } catch (JsonProcessingException ex) {
            throw new TaskExecutionException(TaskErrorCode.HANDLER_FAILED, "报告 JSON 序列化失败", ex);
        }
    }

    private String htmlReport(ReportView report, Map<String, Object> summary, String riskLevel, List<ReportRepository.ReportInputSnapshot> snapshots) {
        StringBuilder html = new StringBuilder();
        html.append("<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><title>")
                .append(escape(report.title()))
                .append("</title><style>body{font-family:Arial,sans-serif;margin:24px;color:#172033;background:#fff}.header{display:flex;align-items:center;gap:18px;margin-bottom:18px}.header svg{width:121px;height:33px}.meta{color:#5f6b7a}.cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:18px 0}.card{border:1px solid #d8dee8;border-radius:6px;padding:12px}.card strong{display:block;font-size:22px;margin-top:6px}.risk{font-weight:700}.section{margin-top:22px}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #d8dee8;padding:8px;text-align:left;vertical-align:top}th{background:#f4f6fa}ul{margin-top:8px}</style></head><body>");
        html.append("<div class=\"header\">").append(LOGO_SVG).append("<div><h1>").append(escape(report.title())).append("</h1>")
                .append("<div class=\"meta\">迁移评估报告</div></div></div>");
        html.append("<div class=\"cards\">")
                .append(card("总体风险", riskLevel))
                .append(card("确认输入", summary.get("confirmedInputCount")))
                .append(card("高风险问题", summary.get("highRiskIssueCount")))
                .append(card("预计工作量", workloadText(summary.get("estimatedWorkload"))))
                .append("</div>");
        html.append("<div class=\"section\"><h2>主要风险和优先处理项</h2>");
        appendIssueList(html, summary.get("priorityIssues"));
        html.append("</div>");
        html.append("<div class=\"section\"><h2>依赖替代性注意点</h2>");
        appendIssueList(html, summary.get("dependencySubstitutionNotes"));
        html.append("</div>");
        appendOrganization(html, ReportDocumentOrganizer.organize(snapshots));
        html.append("<div class=\"section\"><h2>原始证据附录</h2>");
        html.append("<table><thead><tr><th>问题</th><th>来源</th><th>等级</th><th>目标状态</th><th>依赖类型</th><th>位置/组件</th><th>建议</th><th>证据摘要</th><th>备注</th></tr></thead><tbody>");
        for (ReportRepository.ReportInputSnapshot item : snapshots) {
            Map<String, Object> snapshot = item.snapshot();
            Map<String, Object> sourceDetail = mapValue(snapshot.get("sourceDetail"));
            html.append("<tr>")
                    .append("<td>").append(escape(snapshot.get("issueTitle"))).append("</td>")
                    .append("<td>").append(escape(snapshot.get("sourceType"))).append("</td>")
                    .append("<td>").append(escape(snapshot.get("detectedLevel"))).append("</td>")
                    .append("<td>").append(escape(firstNonBlank(stringValue(sourceDetail.get("targetMatchStatus")), statusToken(stringValue(snapshot.get("detectedLevel")))))).append("</td>")
                    .append("<td>").append(escape(sourceDetail.get("dependencyType"))).append("</td>")
                    .append("<td>").append(escape(snapshot.get("locationLabel"))).append("</td>")
                    .append("<td>").append(escape(snapshot.get("recommendationSummary"))).append("</td>")
                    .append("<td>").append(escape(evidenceSummary(sourceDetail.get("evidence")))).append("</td>")
                    .append("<td>").append(escape(snapshot.get("note"))).append("</td>")
                    .append("</tr>");
        }
        html.append("</tbody></table></div></body></html>");
        return html.toString();
    }

    @SuppressWarnings("unchecked")
    private void appendOrganization(StringBuilder html, Map<String, Object> organization) {
        html.append("<div class=\"section\"><h2>源码迁移问题</h2>");
        Object modulesValue = organization.get("codeModules");
        if (!(modulesValue instanceof List<?> modules) || modules.isEmpty()) {
            html.append("<p>暂无源码迁移问题。</p></div>");
        } else {
            for (Object moduleValue : modules) {
                Map<String, Object> module = mapValue(moduleValue);
                html.append("<details open><summary><strong>").append(escape(module.get("moduleName")))
                        .append("</strong> · ").append(escape(module.get("fileCount"))).append(" 个文件 · ")
                        .append(escape(module.get("findingCount"))).append(" 个问题 · 最高风险 ")
                        .append(escape(module.get("highestRisk"))).append("</summary>");
                Object filesValue = module.get("files");
                if (filesValue instanceof List<?> files) {
                    for (Object fileValue : files) {
                        Map<String, Object> file = mapValue(fileValue);
                        html.append("<details><summary>").append(escape(file.get("relativePath")))
                                .append(" · ").append(escape(file.get("findingCount"))).append(" 个问题</summary>");
                        Object typesValue = file.get("findingTypes");
                        if (typesValue instanceof List<?> types) {
                            for (Object typeValue : types) {
                                Map<String, Object> type = mapValue(typeValue);
                                html.append("<details><summary>").append(escape(type.get("findingType"))).append(": ")
                                        .append(escape(type.get("findingCount"))).append(" 个，行 ")
                                        .append(escape(type.get("firstLine"))).append("-").append(escape(type.get("lastLine")))
                                        .append("，最高风险 ").append(escape(type.get("highestRisk"))).append("</summary>");
                                Object findingsValue = type.get("findings");
                                if (findingsValue instanceof List<?> findings) {
                                    html.append("<ul>");
                                    for (Object findingValue : findings) {
                                        Map<String, Object> finding = mapValue(findingValue);
                                        html.append("<li>行 ").append(escape(finding.get("lineStart"))).append("-")
                                                .append(escape(finding.get("lineEnd"))).append(" · ")
                                                .append(escape(finding.get("riskLevel"))).append(" · ")
                                                .append(escape(finding.get("issueTitle"))).append("</li>");
                                    }
                                    html.append("</ul>");
                                }
                                html.append("</details>");
                            }
                        }
                        html.append("</details>");
                    }
                }
                html.append("</details>");
            }
            html.append("</div>");
        }
        html.append("<div class=\"section\"><h2>全局依赖迁移列表</h2>");
        Object dependenciesValue = organization.get("dependencyPackages");
        if (!(dependenciesValue instanceof List<?> dependencies) || dependencies.isEmpty()) {
            html.append("<p>暂无依赖迁移项。</p>");
        } else {
            html.append("<table><thead><tr><th>软件包</th><th>源版本</th><th>目标版本</th><th>最高风险</th><th>目标状态</th><th>依赖类型</th></tr></thead><tbody>");
            for (Object dependencyValue : dependencies) {
                Map<String, Object> dependency = mapValue(dependencyValue);
                html.append("<tr><td>").append(escape(dependency.get("packageName"))).append("</td><td>")
                        .append(escape(dependency.get("sourceVersion"))).append("</td><td>")
                        .append(escape(dependency.get("targetVersion"))).append("</td><td>")
                        .append(escape(dependency.get("highestRisk"))).append("</td><td>")
                        .append(escape(dependency.get("targetMatchStatuses"))).append("</td><td>")
                        .append(escape(dependency.get("dependencyTypes"))).append("</td></tr>");
            }
            html.append("</tbody></table>");
        }
        html.append("</div>");
    }

    private long highRiskIssueCount(List<MigrationInputRefView> refs) {
        return refs.stream()
                .map(ref -> riskToken(ref.detectedLevel()))
                .filter(risk -> "CRITICAL".equals(risk) || "HIGH".equals(risk))
                .count();
    }

    private Map<String, Object> estimatedWorkload(List<MigrationInputRefView> refs) {
        double min = 0;
        double max = 0;
        Map<String, Long> byRisk = refs.stream()
                .collect(java.util.stream.Collectors.groupingBy(ref -> riskToken(ref.detectedLevel()), LinkedHashMap::new, java.util.stream.Collectors.counting()));
        for (MigrationInputRefView ref : refs) {
            double[] range = workloadRange(riskToken(ref.detectedLevel()));
            min += range[0];
            max += range[1];
        }
        Map<String, Object> workload = new LinkedHashMap<>();
        workload.put("unit", "person_hour");
        workload.put("method", "基于已确认迁移输入风险等级的初步估算");
        workload.put("min", roundOne(min));
        workload.put("max", roundOne(max));
        workload.put("byRisk", byRisk);
        return workload;
    }

    private double[] workloadRange(String risk) {
        return switch (risk) {
            case "CRITICAL" -> new double[]{4, 8};
            case "HIGH" -> new double[]{2, 4};
            case "MEDIUM" -> new double[]{1, 2};
            case "LOW" -> new double[]{0.5, 1};
            default -> new double[]{0.25, 0.5};
        };
    }

    private double roundOne(double value) {
        return Math.round(value * 10.0) / 10.0;
    }

    private List<Map<String, Object>> priorityIssues(List<MigrationInputRefView> refs) {
        return refs.stream()
                .sorted(Comparator.comparingInt((MigrationInputRefView ref) -> riskRank(riskToken(ref.detectedLevel())))
                        .thenComparing(MigrationInputRefView::createdAt, Comparator.nullsLast(Comparator.naturalOrder())))
                .limit(PRIORITY_LIMIT)
                .map(this::issueSummary)
                .toList();
    }

    private List<Map<String, Object>> dependencySubstitutionNotes(List<MigrationInputRefView> refs) {
        return refs.stream()
                .filter(ref -> ref.sourceType() == cn.rvport.backend.migration.MigrationInputSourceType.DEPENDENCY_RESULT || isDependencyLocation(ref.locationLabel()) || statusToken(ref.detectedLevel()) != null)
                .sorted(Comparator.comparingInt((MigrationInputRefView ref) -> riskRank(riskToken(ref.detectedLevel())))
                        .thenComparing(MigrationInputRefView::issueTitle, Comparator.nullsLast(String::compareToIgnoreCase)))
                .limit(PRIORITY_LIMIT)
                .map(ref -> {
                    Map<String, Object> value = issueSummary(ref);
                    value.put("targetMatchStatus", defaultText(statusToken(ref.detectedLevel()), "UNKNOWN"));
                    value.put("note", dependencyNote(ref));
                    if ("DEPENDENCY_RESULT".equals(ref.sourceType().name())) {
                        Map<String, Object> detail = sourceResolver.detail(ref);
                        value.put("dependencyType", detail.get("dependencyType"));
                        value.put("dependencyName", detail.get("dependencyName"));
                        value.put("dependencyVersion", detail.get("dependencyVersion"));
                        value.put("riskLevel", detail.get("riskLevel"));
                        value.put("recommendation", detail.get("recommendation"));
                        value.put("evidenceSummary", evidenceSummary(detail.get("evidence")));
                    }
                    return value;
                })
                .toList();
    }

    private List<MigrationInputRefView> dependencyRefs(List<MigrationInputRefView> refs) {
        return refs.stream()
                .filter(ref -> "DEPENDENCY_RESULT".equals(ref.sourceType().name()))
                .toList();
    }

    private Map<String, Long> dependencyRiskCounts(List<MigrationInputRefView> refs) {
        return dependencyRefs(refs).stream()
                .collect(java.util.stream.Collectors.groupingBy(ref -> riskToken(ref.detectedLevel()), LinkedHashMap::new, java.util.stream.Collectors.counting()));
    }

    private Map<String, Long> dependencyTargetMatchStatusCounts(List<MigrationInputRefView> refs) {
        return dependencyRefs(refs).stream()
                .collect(java.util.stream.Collectors.groupingBy(ref -> defaultText(statusToken(ref.detectedLevel()), "UNKNOWN"), LinkedHashMap::new, java.util.stream.Collectors.counting()));
    }

    private Map<String, Object> issueSummary(MigrationInputRefView ref) {
        Map<String, Object> value = new LinkedHashMap<>();
        value.put("id", ref.id());
        value.put("sourceType", ref.sourceType().name());
        value.put("issueTitle", ref.issueTitle());
        value.put("detectedLevel", ref.detectedLevel());
        value.put("locationLabel", ref.locationLabel());
        value.put("recommendationSummary", ref.recommendationSummary());
        return value;
    }

    private boolean isDependencyLocation(String locationLabel) {
        String value = defaultText(locationLabel, "").toLowerCase(Locale.ROOT);
        return value.startsWith("package:") || value.startsWith("lib:");
    }

    private String statusToken(String detectedLevel) {
        String value = defaultText(detectedLevel, "").toUpperCase(Locale.ROOT);
        int slash = value.indexOf('/');
        return slash < 0 || slash == value.length() - 1 ? null : value.substring(slash + 1);
    }

    private String dependencyNote(MigrationInputRefView ref) {
        String status = defaultText(statusToken(ref.detectedLevel()), "UNKNOWN");
        return switch (status) {
            case "TARGET_INSTALLED", "TARGET_PRESENT" -> "目标环境已有可用替代，优先确认版本、ABI 和调用方式。";
            case "REPO_AVAILABLE" -> "目标仓库存在候选包，建议安装后复跑构建验证。";
            case "PROVIDES_MATCH" -> "目标环境存在 provider 匹配，建议确认 provider 包和路径。";
            case "SOURCE_BUILD_REQUIRED" -> "目标源或已安装包未直接覆盖，需要评估源码构建成本。";
            case "MANUAL_REVIEW", "MANUAL_CONFIRM_REQUIRED" -> "自动匹配不足，需要人工确认包名、库名或版本等价关系。";
            case "MISSING", "TARGET_MISSING", "NO_ALTERNATIVE" -> "目标环境缺少直接替代，需要优先确认替代方案或移植策略。";
            default -> isDependencyLocation(ref.locationLabel()) ? "依赖项需要确认目标环境替代性。" : "需要结合来源详情确认处理方式。";
        };
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> mapValue(Object value) {
        if (value instanceof Map<?, ?> map) {
            Map<String, Object> result = new LinkedHashMap<>();
            map.forEach((key, item) -> result.put(String.valueOf(key), item));
            return result;
        }
        return Map.of();
    }

    private String stringValue(Object value) {
        return value == null ? "" : String.valueOf(value);
    }

    private String firstNonBlank(String... values) {
        for (String value : values) {
            if (value != null && !value.isBlank()) {
                return value;
            }
        }
        return "";
    }

    private String evidenceSummary(Object evidence) {
        if (!(evidence instanceof Map<?, ?> map) || map.isEmpty()) {
            return "";
        }
        Object source = map.get("source");
        Object match = map.get("targetMatchEvidence");
        if (match instanceof Map<?, ?> matchMap && !matchMap.isEmpty()) {
            Object matchedBy = matchMap.get("matchedBy");
            Object name = matchMap.get("name");
            Object version = matchMap.get("version");
            return "source=" + source + ", matchedBy=" + matchedBy + ", target=" + name
                    + (version == null ? "" : "@" + version);
        }
        return "source=" + source;
    }

    private String card(String label, Object value) {
        return "<div class=\"card\"><span>" + escape(label) + "</span><strong>" + escape(value) + "</strong></div>";
    }

    @SuppressWarnings("unchecked")
    private String workloadText(Object workload) {
        if (!(workload instanceof Map<?, ?> map)) {
            return "";
        }
        Object min = map.get("min");
        Object max = map.get("max");
        return min + "-" + max + " 人时";
    }

    @SuppressWarnings("unchecked")
    private void appendIssueList(StringBuilder html, Object issues) {
        if (!(issues instanceof List<?> list) || list.isEmpty()) {
            html.append("<p>暂无。</p>");
            return;
        }
        html.append("<ul>");
        for (Object item : list) {
            if (item instanceof Map<?, ?> map) {
                html.append("<li><span class=\"risk\">").append(escape(map.get("detectedLevel"))).append("</span> ")
                        .append(escape(map.get("issueTitle"))).append(" - ")
                        .append(escape(map.get("locationLabel")));
                Object note = map.get("note");
                if (note != null) {
                    html.append("；").append(escape(note));
                }
                html.append("</li>");
            }
        }
        html.append("</ul>");
    }

    private StoredArtifactView saveJson(ReportView report, Map<String, Object> content, byte[] bytes, Map<String, Object> summary, TaskExecutionContext context) {
        return storedArtifactService.storeJson(
                report.projectId(),
                report.taskId(),
                StoredArtifactOwnerType.MIGRATION_REPORT,
                report.id(),
                ReportDownloadFormat.JSON.artifactType(),
                content,
                Map.of("format", "JSON", "sizeBytes", bytes.length, "summary", summary), context
        );
    }

    private StoredArtifactView saveHtml(ReportView report, byte[] bytes, Map<String, Object> summary, TaskExecutionContext context) {
        return storedArtifactService.store(new StoredArtifactCreateCommand(
                report.projectId(),
                report.taskId(),
                StoredArtifactOwnerType.MIGRATION_REPORT,
                report.id(),
                ReportDownloadFormat.HTML.artifactType(),
                ReportDownloadFormat.HTML.contentType(),
                bytes,
                Map.of("format", "HTML", "sizeBytes", bytes.length, "summary", summary),
                ReportDownloadFormat.HTML.extension()
        ), context);
    }

    private void failReport(TaskExecutionContext context, ReportView report, TaskStatus status, Map<String, Object> summary) {
        context.publish(() -> reportStatusWriter.updateStatus(report.id(), status, summary));
        cleanupArtifacts(report, context);
    }

    private void cleanupArtifacts(ReportView report, TaskExecutionContext context) {
        try {
            storedArtifactRepository.listByOwner(StoredArtifactOwnerType.MIGRATION_REPORT, report.id())
                    .forEach(artifact -> storedArtifactService.delete(artifact, context));
        } catch (TaskAttemptLostException ex) {
            throw ex;
        } catch (RuntimeException ignored) {
            // 失败路径尽力清理，不能覆盖原始任务错误。
        }
    }

    private Map<String, Object> failureSummary(String errorCode, String message, String failureStage, Throwable cause) {
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("schemaVersion", SCHEMA_VERSION);
        summary.put("phase", "FAILED");
        summary.put("errorCode", defaultText(errorCode, TaskErrorCode.HANDLER_FAILED));
        summary.put("errorMessage", sanitize(message));
        summary.put("failureStage", defaultText(failureStage, "UNKNOWN"));
        if (cause != null) {
            summary.put("causeClass", cause.getClass().getName());
            summary.put("causeMessage", sanitize(cause.getMessage()));
        }
        summary.put("failedAt", OffsetDateTime.now());
        return summary;
    }

    private RuntimeException sanitizedThrowable(RuntimeException ex) {
        RuntimeException sanitized = new RuntimeException(sanitize(ex.getMessage()), sanitizedCause(ex.getCause()));
        sanitized.setStackTrace(ex.getStackTrace());
        return sanitized;
    }

    private Throwable sanitizedCause(Throwable cause) {
        if (cause == null) {
            return null;
        }
        RuntimeException sanitized = new RuntimeException(sanitize(cause.getMessage()));
        sanitized.setStackTrace(cause.getStackTrace());
        return sanitized;
    }

    private String sanitize(String value) {
        if (value == null || value.isBlank()) {
            return "";
        }
        String sanitized = value
                .replace('\\', '/')
                .replaceAll("(?i)(password|private[_-]?key|passphrase|secret|token)(\\s*[=:]\\s*)\\S+", "$1$2[REDACTED]")
                .replaceAll("(?i)authorization:\\s*bearer\\s+\\S+", "Authorization: Bearer [REDACTED]")
                .replaceAll("(?i)[A-Za-z]:/[^\\s]+", "<server-path-redacted>")
                .replaceAll("(^|\\s)/[^\\s]+", "$1<server-path-redacted>")
                .replace("../", "<parent-path-redacted>/");
        return sanitized.length() > 500 ? sanitized.substring(0, 500) : sanitized;
    }

    private String defaultText(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value.trim();
    }

    private String escape(Object value) {
        if (value == null) {
            return "";
        }
        return value.toString()
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\"", "&quot;")
                .replace("'", "&#39;");
    }
}
