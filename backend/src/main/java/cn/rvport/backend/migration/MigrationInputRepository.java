package cn.rvport.backend.migration;

import static cn.rvport.backend.jooq.tables.MigrationInputRefs.MIGRATION_INPUT_REFS;
import static cn.rvport.backend.jooq.tables.MigrationInputSets.MIGRATION_INPUT_SETS;

import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.jooq.Condition;
import org.jooq.DSLContext;
import org.jooq.Field;
import org.jooq.SortField;
import org.jooq.impl.DSL;
import org.springframework.stereotype.Repository;

@Repository
public class MigrationInputRepository {

    private final DSLContext dsl;

    public MigrationInputRepository(DSLContext dsl) {
        this.dsl = dsl;
    }

    public UUID ensureActiveSet(UUID projectId, UUID sourceRevisionId) {
        dsl.insertInto(MIGRATION_INPUT_SETS)
                .set(MIGRATION_INPUT_SETS.PROJECT_ID, projectId)
                .set(MIGRATION_INPUT_SETS.SOURCE_REVISION_ID, sourceRevisionId)
                .set(MIGRATION_INPUT_SETS.STATUS, MigrationInputSetStatus.ACTIVE.name())
                .onConflictDoNothing()
                .execute();
        return dsl.select(MIGRATION_INPUT_SETS.ID)
                .from(MIGRATION_INPUT_SETS)
                .where(MIGRATION_INPUT_SETS.PROJECT_ID.eq(projectId)
                        .and(MIGRATION_INPUT_SETS.SOURCE_REVISION_ID.eq(sourceRevisionId))
                        .and(MIGRATION_INPUT_SETS.STATUS.eq(MigrationInputSetStatus.ACTIVE.name())))
                .fetchOne(MIGRATION_INPUT_SETS.ID);
    }

    public long count(UUID projectId, UUID sourceRevisionId, MigrationInputListRequest request) {
        return dsl.selectCount()
                .from(MIGRATION_INPUT_REFS)
                .where(filter(projectId, sourceRevisionId, request))
                .fetchOne(0, long.class);
    }

    public List<MigrationInputRefView> list(UUID projectId, UUID sourceRevisionId, MigrationInputListRequest request) {
        int page = request.normalizedPage();
        int pageSize = request.normalizedPageSize();
        return dsl.selectFrom(MIGRATION_INPUT_REFS)
                .where(filter(projectId, sourceRevisionId, request))
                .orderBy(sort(request))
                .limit(pageSize)
                .offset((page - 1) * pageSize)
                .fetch(MigrationInputRefView::from);
    }

    public Optional<MigrationInputRefView> findById(UUID id) {
        return dsl.selectFrom(MIGRATION_INPUT_REFS)
                .where(MIGRATION_INPUT_REFS.ID.eq(id))
                .fetchOptional(MigrationInputRefView::from);
    }

    public InsertResult insertCandidates(UUID inputSetId, List<MigrationInputCandidate> candidates) {
        List<MigrationInputRefView> createdItems = new ArrayList<>();
        int skipped = 0;
        for (MigrationInputCandidate candidate : candidates) {
            var record = dsl.insertInto(MIGRATION_INPUT_REFS)
                    .set(MIGRATION_INPUT_REFS.INPUT_SET_ID, inputSetId)
                    .set(MIGRATION_INPUT_REFS.PROJECT_ID, candidate.projectId())
                    .set(MIGRATION_INPUT_REFS.SOURCE_REVISION_ID, candidate.sourceRevisionId())
                    .set(MIGRATION_INPUT_REFS.ISSUE_TITLE, candidate.issueTitle())
                    .set(MIGRATION_INPUT_REFS.SOURCE_TYPE, candidate.sourceType().name())
                    .set(MIGRATION_INPUT_REFS.SOURCE_REF_ID, candidate.sourceRefId())
                    .set(MIGRATION_INPUT_REFS.DETECTED_LEVEL, candidate.detectedLevel())
                    .set(MIGRATION_INPUT_REFS.LOCATION_LABEL, blankToNull(candidate.locationLabel()))
                    .set(MIGRATION_INPUT_REFS.RECOMMENDATION_SUMMARY, blankToNull(candidate.recommendationSummary()))
                    .set(MIGRATION_INPUT_REFS.RULE_ID, blankToNull(candidate.ruleId()))
                    .set(MIGRATION_INPUT_REFS.IDENTITY_PATH, blankToNull(candidate.identityPath()))
                    .set(MIGRATION_INPUT_REFS.IDENTITY_SYMBOL, blankToNull(candidate.identitySymbol()))
                    .set(MIGRATION_INPUT_REFS.IDENTITY_ANCHOR, blankToNull(candidate.identityAnchor()))
                    .set(MIGRATION_INPUT_REFS.STABLE_FINGERPRINT, blankToNull(candidate.stableFingerprint()))
                    .set(MIGRATION_INPUT_REFS.STATUS, defaultStatus(candidate).name())
                    .onConflict(MIGRATION_INPUT_REFS.INPUT_SET_ID, MIGRATION_INPUT_REFS.SOURCE_TYPE, MIGRATION_INPUT_REFS.SOURCE_REF_ID)
                    .doNothing()
                    .returning()
                    .fetchOne();
            if (record == null) {
                skipped++;
            } else {
                createdItems.add(MigrationInputRefView.from(record));
            }
        }
        return new InsertResult(createdItems, skipped);
    }

    public int deleteBySourceType(UUID projectId, UUID sourceRevisionId, MigrationInputSourceType sourceType) {
        return dsl.deleteFrom(MIGRATION_INPUT_REFS)
                .where(MIGRATION_INPUT_REFS.PROJECT_ID.eq(projectId)
                        .and(MIGRATION_INPUT_REFS.SOURCE_REVISION_ID.eq(sourceRevisionId))
                        .and(MIGRATION_INPUT_REFS.SOURCE_TYPE.eq(sourceType.name())))
                .execute();
    }

    public MigrationInputRefView update(UUID id, MigrationInputStatus status, String note) {
        var update = dsl.update(MIGRATION_INPUT_REFS)
                .set(MIGRATION_INPUT_REFS.UPDATED_AT, OffsetDateTime.now());
        if (status != null) {
            update = update.set(MIGRATION_INPUT_REFS.STATUS, status.name());
        }
        if (note != null) {
            update = update.set(MIGRATION_INPUT_REFS.NOTE, blankToNull(note));
        }
        var record = update.where(MIGRATION_INPUT_REFS.ID.eq(id))
                .returning()
                .fetchOne();
        return record == null ? null : MigrationInputRefView.from(record);
    }

    public List<MigrationInputRefView> confirmedRefs(UUID projectId, UUID sourceRevisionId) {
        return dsl.selectFrom(MIGRATION_INPUT_REFS)
                .where(MIGRATION_INPUT_REFS.PROJECT_ID.eq(projectId)
                        .and(MIGRATION_INPUT_REFS.SOURCE_REVISION_ID.eq(sourceRevisionId))
                        .and(MIGRATION_INPUT_REFS.STATUS.eq(MigrationInputStatus.CONFIRMED.name())))
                .orderBy(MIGRATION_INPUT_REFS.CREATED_AT.asc(), MIGRATION_INPUT_REFS.ID.asc())
                .fetch(MigrationInputRefView::from);
    }

    public List<MigrationInputRefView> listAll(UUID projectId, UUID sourceRevisionId) {
        return dsl.selectFrom(MIGRATION_INPUT_REFS)
                .where(MIGRATION_INPUT_REFS.PROJECT_ID.eq(projectId)
                        .and(MIGRATION_INPUT_REFS.SOURCE_REVISION_ID.eq(sourceRevisionId)))
                .orderBy(MIGRATION_INPUT_REFS.UPDATED_AT.desc().nullsLast(), MIGRATION_INPUT_REFS.CREATED_AT.desc(), MIGRATION_INPUT_REFS.ID.desc())
                .fetch(MigrationInputRefView::from);
    }

    public Map<UUID, MigrationInputRefView> findBySourceRefs(
            UUID projectId,
            UUID sourceRevisionId,
            MigrationInputSourceType sourceType,
            List<UUID> sourceRefIds
    ) {
        if (sourceRefIds == null || sourceRefIds.isEmpty()) {
            return Map.of();
        }
        Map<UUID, MigrationInputRefView> result = new LinkedHashMap<>();
        dsl.selectFrom(MIGRATION_INPUT_REFS)
                .where(MIGRATION_INPUT_REFS.PROJECT_ID.eq(projectId)
                        .and(MIGRATION_INPUT_REFS.SOURCE_REVISION_ID.eq(sourceRevisionId))
                        .and(MIGRATION_INPUT_REFS.SOURCE_TYPE.eq(sourceType.name()))
                        .and(MIGRATION_INPUT_REFS.SOURCE_REF_ID.in(sourceRefIds)))
                .fetch(MigrationInputRefView::from)
                .forEach(ref -> result.put(ref.sourceRefId(), ref));
        return result;
    }

    private Condition filter(UUID projectId, UUID sourceRevisionId, MigrationInputListRequest request) {
        Condition condition = MIGRATION_INPUT_REFS.PROJECT_ID.eq(projectId)
                .and(MIGRATION_INPUT_REFS.SOURCE_REVISION_ID.eq(sourceRevisionId));
        if (request.sourceType() != null) {
            condition = condition.and(MIGRATION_INPUT_REFS.SOURCE_TYPE.eq(request.sourceType().name()));
        }
        condition = textEquals(condition, MIGRATION_INPUT_REFS.DETECTED_LEVEL, request.detectedLevel());
        if (request.status() != null) {
            condition = condition.and(MIGRATION_INPUT_REFS.STATUS.eq(request.status().name()));
        }
        String keyword = blankToNull(request.keyword());
        if (keyword != null) {
            condition = condition.and(MIGRATION_INPUT_REFS.ISSUE_TITLE.containsIgnoreCase(keyword)
                    .or(MIGRATION_INPUT_REFS.LOCATION_LABEL.containsIgnoreCase(keyword))
                    .or(MIGRATION_INPUT_REFS.RECOMMENDATION_SUMMARY.containsIgnoreCase(keyword)));
        }
        return condition;
    }

    private List<SortField<?>> sort(MigrationInputListRequest request) {
        Field<?> field = switch (blankToDefault(request.sortBy(), "")) {
            case "createdAt" -> MIGRATION_INPUT_REFS.CREATED_AT;
            case "updatedAt" -> MIGRATION_INPUT_REFS.UPDATED_AT;
            case "sourceType" -> MIGRATION_INPUT_REFS.SOURCE_TYPE;
            case "detectedLevel" -> MIGRATION_INPUT_REFS.DETECTED_LEVEL;
            case "status" -> MIGRATION_INPUT_REFS.STATUS;
            case "issueTitle" -> MIGRATION_INPUT_REFS.ISSUE_TITLE;
            case "" -> null;
            default -> throw new IllegalArgumentException("Unsupported migration input sort field: " + request.sortBy());
        };
        if (field == null) {
            return List.of(MIGRATION_INPUT_REFS.CREATED_AT.desc(), MIGRATION_INPUT_REFS.ID.desc());
        }
        return List.of("desc".equalsIgnoreCase(request.sortDirection()) ? field.desc().nullsLast() : field.asc().nullsLast(), MIGRATION_INPUT_REFS.ID.asc());
    }

    private Condition textEquals(Condition condition, Field<String> field, String value) {
        String normalized = blankToNull(value);
        return normalized == null ? condition : condition.and(field.eq(normalized));
    }

    private String blankToDefault(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value.trim();
    }

    private String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }

    public record InsertResult(List<MigrationInputRefView> createdItems, int skipped) {
    }

    private MigrationInputStatus defaultStatus(MigrationInputCandidate candidate) {
        return candidate.initialStatus() == null ? MigrationInputStatus.CANDIDATE : candidate.initialStatus();
    }
}
