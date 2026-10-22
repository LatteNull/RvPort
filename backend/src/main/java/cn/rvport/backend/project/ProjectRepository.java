package cn.rvport.backend.project;

import static cn.rvport.backend.jooq.tables.Projects.PROJECTS;
import static cn.rvport.backend.jooq.tables.BuildRuns.BUILD_RUNS;
import static cn.rvport.backend.jooq.tables.Findings.FINDINGS;
import static cn.rvport.backend.jooq.tables.KbScanRuns.KB_SCAN_RUNS;
import static cn.rvport.backend.jooq.tables.TestRuns.TEST_RUNS;

import cn.rvport.backend.jooq.tables.records.ProjectsRecord;
import java.time.OffsetDateTime;
import java.util.Collection;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.jooq.Condition;
import org.jooq.DSLContext;
import org.jooq.Field;
import org.jooq.impl.DSL;
import org.springframework.stereotype.Repository;

@Repository
public class ProjectRepository {

    private final DSLContext dsl;

    public ProjectRepository(DSLContext dsl) {
        this.dsl = dsl;
    }

    public ProjectView create(String name, String description, String sourceArch, String targetArch, UUID createdBy) {
        ProjectsRecord record = dsl.insertInto(PROJECTS)
                .set(PROJECTS.NAME, name)
                .set(PROJECTS.DESCRIPTION, description)
                .set(PROJECTS.SOURCE_ARCH, sourceArch)
                .set(PROJECTS.TARGET_ARCH, targetArch)
                .set(PROJECTS.STAGE, ProjectStage.PROJECT_CREATED.name())
                .set(PROJECTS.STATUS, ProjectStatus.ACTIVE.name())
                .set(PROJECTS.CREATED_BY, createdBy)
                .returning()
                .fetchOne();
        return ProjectView.from(record);
    }

    public Optional<ProjectView> findById(UUID projectId) {
        return dsl.selectFrom(PROJECTS)
                .where(PROJECTS.ID.eq(projectId).and(PROJECTS.DELETED_AT.isNull()))
                .fetchOptional()
                .map(ProjectView::from);
    }

    public long count(ProjectStatus status, ProjectStage stage, String keyword) {
        return dsl.selectCount()
                .from(PROJECTS)
                .where(filter(status, stage, keyword))
                .fetchOne(0, long.class);
    }

    public long countAccessible(ProjectStatus status, ProjectStage stage, String keyword, UUID actorUserId, boolean superAdmin) {
        return dsl.selectCount()
                .from(PROJECTS)
                .where(accessibleFilter(status, stage, keyword, actorUserId, superAdmin))
                .fetchOne(0, long.class);
    }

    public List<ProjectView> list(ProjectStatus status, ProjectStage stage, String keyword, int page, int pageSize) {
        return dsl.selectFrom(PROJECTS)
                .where(filter(status, stage, keyword))
                .orderBy(PROJECTS.UPDATED_AT.desc().nullsLast(), PROJECTS.CREATED_AT.desc())
                .limit(pageSize)
                .offset((page - 1) * pageSize)
                .fetch(ProjectView::from);
    }

    public List<ProjectView> listAccessible(ProjectStatus status, ProjectStage stage, String keyword, int page, int pageSize, UUID actorUserId, boolean superAdmin) {
        return dsl.selectFrom(PROJECTS)
                .where(accessibleFilter(status, stage, keyword, actorUserId, superAdmin))
                .orderBy(PROJECTS.UPDATED_AT.desc().nullsLast(), PROJECTS.CREATED_AT.desc())
                .limit(pageSize)
                .offset((page - 1) * pageSize)
                .fetch(ProjectView::from);
    }

    public Map<UUID, ProjectSummaryView> summaries(Collection<UUID> projectIds) {
        Map<UUID, ProjectSummaryView> summaries = new HashMap<>();
        for (UUID projectId : projectIds) {
            summaries.put(projectId, ProjectSummaryView.empty());
        }
        if (summaries.isEmpty()) {
            return summaries;
        }

        addFindingRiskCounts(summaries);
        addLatestKbScanAt(summaries);
        addLatestBuildStatus(summaries);
        addLatestTestStatus(summaries);
        return summaries;
    }

    public ProjectView update(
            UUID projectId,
            String name,
            String description,
            String sourceArch,
            String targetArch,
            ProjectStatus status
    ) {
        ProjectsRecord record = dsl.update(PROJECTS)
                .set(PROJECTS.NAME, name)
                .set(PROJECTS.DESCRIPTION, description)
                .set(PROJECTS.SOURCE_ARCH, sourceArch)
                .set(PROJECTS.TARGET_ARCH, targetArch)
                .set(PROJECTS.STATUS, status.name())
                .set(PROJECTS.UPDATED_AT, OffsetDateTime.now())
                .where(PROJECTS.ID.eq(projectId).and(PROJECTS.DELETED_AT.isNull()))
                .returning()
                .fetchOne();
        return record == null ? null : ProjectView.from(record);
    }

    public void updateStage(UUID projectId, ProjectStage stage) {
        dsl.update(PROJECTS)
                .set(PROJECTS.STAGE, stage.name())
                .set(PROJECTS.UPDATED_AT, OffsetDateTime.now())
                .where(PROJECTS.ID.eq(projectId).and(PROJECTS.DELETED_AT.isNull()))
                .execute();
    }

    public void lockSourceInputTypeIfEmpty(UUID projectId, ProjectSourceInputType sourceInputType) {
        dsl.update(PROJECTS)
                .set(PROJECTS.SOURCE_INPUT_TYPE, sourceInputType.name())
                .set(PROJECTS.UPDATED_AT, OffsetDateTime.now())
                .where(PROJECTS.ID.eq(projectId)
                        .and(PROJECTS.DELETED_AT.isNull())
                        .and(PROJECTS.SOURCE_INPUT_TYPE.isNull()))
                .execute();
    }

    private Condition filter(ProjectStatus status, ProjectStage stage, String keyword) {
        Condition condition = PROJECTS.DELETED_AT.isNull();
        if (status != null) {
            condition = condition.and(PROJECTS.STATUS.eq(status.name()));
        }
        if (stage != null) {
            condition = condition.and(PROJECTS.STAGE.eq(stage.name()));
        }
        if (keyword != null && !keyword.isBlank()) {
            String like = "%" + keyword.trim().toLowerCase() + "%";
            condition = condition.and(DSL.lower(PROJECTS.NAME).like(like)
                    .or(DSL.lower(PROJECTS.DESCRIPTION).like(like)));
        }
        return condition;
    }

    private Condition accessibleFilter(ProjectStatus status, ProjectStage stage, String keyword, UUID actorUserId, boolean superAdmin) {
        Condition condition = filter(status, stage, keyword);
        if (!superAdmin) {
            condition = condition.and(PROJECTS.CREATED_BY.eq(actorUserId));
        }
        return condition;
    }

    private void addFindingRiskCounts(Map<UUID, ProjectSummaryView> summaries) {
        dsl.select(FINDINGS.PROJECT_ID, DSL.count())
                .from(FINDINGS)
                .where(FINDINGS.PROJECT_ID.in(summaries.keySet())
                        .and(FINDINGS.STATUS.eq("DETECTED"))
                        .and(FINDINGS.SEVERITY.in("HIGH", "CRITICAL")))
                .groupBy(FINDINGS.PROJECT_ID)
                .fetch()
                .forEach(record -> {
                    UUID projectId = record.get(FINDINGS.PROJECT_ID);
                    summaries.computeIfPresent(projectId, (id, summary) ->
                            summary.withHighRiskCount(summary.highRiskCount() + record.value2()));
                });
    }

    private void addLatestKbScanAt(Map<UUID, ProjectSummaryView> summaries) {
        Field<OffsetDateTime> scanTime = DSL.coalesce(KB_SCAN_RUNS.FINISHED_AT, KB_SCAN_RUNS.STARTED_AT);
        dsl.select(KB_SCAN_RUNS.PROJECT_ID, DSL.max(scanTime))
                .from(KB_SCAN_RUNS)
                .where(KB_SCAN_RUNS.PROJECT_ID.in(summaries.keySet()))
                .groupBy(KB_SCAN_RUNS.PROJECT_ID)
                .fetch()
                .forEach(record -> summaries.computeIfPresent(record.value1(), (id, summary) ->
                        summary.withLatestScanAt(record.value2())));
    }

    private void addLatestBuildStatus(Map<UUID, ProjectSummaryView> summaries) {
        Field<OffsetDateTime> runTime = DSL.coalesce(BUILD_RUNS.FINISHED_AT, BUILD_RUNS.STARTED_AT);
        dsl.select(BUILD_RUNS.PROJECT_ID, BUILD_RUNS.STATUS)
                .from(BUILD_RUNS)
                .where(BUILD_RUNS.PROJECT_ID.in(summaries.keySet()))
                .orderBy(BUILD_RUNS.PROJECT_ID.asc(), runTime.desc().nullsLast())
                .fetch()
                .forEach(record -> summaries.computeIfPresent(record.value1(), (id, summary) ->
                        summary.latestBuildStatus() == null ? summary.withLatestBuildStatus(record.value2()) : summary));
    }

    private void addLatestTestStatus(Map<UUID, ProjectSummaryView> summaries) {
        Field<OffsetDateTime> runTime = DSL.coalesce(TEST_RUNS.FINISHED_AT, TEST_RUNS.STARTED_AT);
        dsl.select(TEST_RUNS.PROJECT_ID, TEST_RUNS.STATUS)
                .from(TEST_RUNS)
                .where(TEST_RUNS.PROJECT_ID.in(summaries.keySet()))
                .orderBy(TEST_RUNS.PROJECT_ID.asc(), runTime.desc().nullsLast())
                .fetch()
                .forEach(record -> summaries.computeIfPresent(record.value1(), (id, summary) ->
                        summary.latestTestStatus() == null ? summary.withLatestTestStatus(record.value2()) : summary));
    }
}
