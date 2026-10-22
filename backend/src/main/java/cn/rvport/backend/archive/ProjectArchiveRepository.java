package cn.rvport.backend.archive;

import static cn.rvport.backend.jooq.tables.ArchiveItems.ARCHIVE_ITEMS;
import static cn.rvport.backend.jooq.tables.Archives.ARCHIVES;
import static cn.rvport.backend.workflow.DomainLatestOrdering.activeFirst;

import cn.rvport.backend.task.TaskStatus;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.jooq.Condition;
import org.jooq.DSLContext;
import org.jooq.Field;
import org.jooq.JSONB;
import org.jooq.SortField;
import org.jooq.impl.DSL;
import org.springframework.stereotype.Repository;

@Repository
public class ProjectArchiveRepository {

    private static final TypeReference<Map<String, Object>> MAP_TYPE = new TypeReference<>() {
    };
    private static final TypeReference<List<ArchiveArtifactRef>> ARTIFACT_REFS_TYPE = new TypeReference<>() {
    };

    private final DSLContext dsl;
    private final ObjectMapper objectMapper;

    public ProjectArchiveRepository(DSLContext dsl, ObjectMapper objectMapper) {
        this.dsl = dsl;
        this.objectMapper = objectMapper;
    }

    public ProjectArchiveView create(UUID projectId, UUID sourceRevisionId, UUID taskId, String name, UUID createdBy) {
        var record = dsl.insertInto(ARCHIVES)
                .set(ARCHIVES.PROJECT_ID, projectId)
                .set(ARCHIVES.SOURCE_REVISION_ID, sourceRevisionId)
                .set(ARCHIVES.TASK_ID, taskId)
                .set(ARCHIVES.NAME, name)
                .set(ARCHIVES.STATUS, TaskStatus.PENDING.name())
                .set(ARCHIVES.SUMMARY, toJsonb(Map.of()))
                .set(ARCHIVES.CREATED_BY, createdBy)
                .returning()
                .fetchOne();
        return toView(record);
    }

    public Optional<ProjectArchiveView> findById(UUID archiveId) {
        return dsl.selectFrom(ARCHIVES)
                .where(ARCHIVES.ID.eq(archiveId))
                .fetchOptional(this::toView);
    }

    public Optional<ProjectArchiveView> findByTaskId(UUID taskId) {
        return dsl.selectFrom(ARCHIVES)
                .where(ARCHIVES.TASK_ID.eq(taskId))
                .fetchOptional(this::toView);
    }

    public Optional<ProjectArchiveView> latest(UUID projectId) {
        return dsl.selectFrom(ARCHIVES)
                .where(ARCHIVES.PROJECT_ID.eq(projectId))
                .orderBy(activeFirst(ARCHIVES.STATUS), ARCHIVES.CREATED_AT.desc(), ARCHIVES.ID.desc())
                .limit(1)
                .fetchOptional(this::toView);
    }

    public Optional<ProjectArchiveView> latest(UUID projectId, UUID sourceRevisionId) {
        Condition condition = ARCHIVES.PROJECT_ID.eq(projectId);
        if (sourceRevisionId != null) {
            condition = condition.and(ARCHIVES.SOURCE_REVISION_ID.eq(sourceRevisionId));
        }
        return dsl.selectFrom(ARCHIVES)
                .where(condition)
                .orderBy(activeFirst(ARCHIVES.STATUS), ARCHIVES.CREATED_AT.desc(), ARCHIVES.ID.desc())
                .limit(1)
                .fetchOptional(this::toView);
    }

    public long count(UUID projectId, ProjectArchiveListRequest request) {
        return dsl.selectCount()
                .from(ARCHIVES)
                .where(filter(projectId, request))
                .fetchOne(0, long.class);
    }

    public List<ProjectArchiveView> list(UUID projectId, ProjectArchiveListRequest request) {
        int page = request.normalizedPage();
        int pageSize = request.normalizedPageSize();
        return dsl.selectFrom(ARCHIVES)
                .where(filter(projectId, request))
                .orderBy(sort(request))
                .limit(pageSize)
                .offset((page - 1) * pageSize)
                .fetch(this::toView);
    }

    public ProjectArchiveItemView createItem(UUID archiveId, ArchiveCandidateView candidate) {
        var record = dsl.insertInto(ARCHIVE_ITEMS)
                .set(ARCHIVE_ITEMS.ARCHIVE_ID, archiveId)
                .set(ARCHIVE_ITEMS.CANDIDATE_ID, candidate.id())
                .set(ARCHIVE_ITEMS.ITEM_TYPE, candidate.nodeType().name())
                .set(ARCHIVE_ITEMS.ITEM_ID, candidate.resourceId())
                .set(ARCHIVE_ITEMS.NODE_TYPE, candidate.nodeType().name())
                .set(ARCHIVE_ITEMS.CANDIDATE_TYPE, candidate.candidateType().name())
                .set(ARCHIVE_ITEMS.CANDIDATE_KEY, candidate.candidateKey())
                .set(ARCHIVE_ITEMS.RESOURCE_TYPE, candidate.resourceType())
                .set(ARCHIVE_ITEMS.RESOURCE_ID, candidate.resourceId())
                .set(ARCHIVE_ITEMS.TITLE, candidate.title())
                .set(ARCHIVE_ITEMS.ARTIFACT_REFS, toJsonb(candidate.artifactRefs()))
                .set(ARCHIVE_ITEMS.METADATA, toJsonb(candidate.summary()))
                .returning()
                .fetchOne();
        return toItemView(record);
    }

    public List<ProjectArchiveItemView> listItems(UUID archiveId) {
        return dsl.selectFrom(ARCHIVE_ITEMS)
                .where(ARCHIVE_ITEMS.ARCHIVE_ID.eq(archiveId))
                .orderBy(ARCHIVE_ITEMS.NODE_TYPE.asc().nullsLast(), ARCHIVE_ITEMS.CANDIDATE_TYPE.asc().nullsLast(), ARCHIVE_ITEMS.CREATED_AT.asc())
                .fetch(this::toItemView);
    }

    public Optional<ProjectArchiveItemView> findItem(UUID archiveId, UUID itemId) {
        return dsl.selectFrom(ARCHIVE_ITEMS)
                .where(ARCHIVE_ITEMS.ARCHIVE_ID.eq(archiveId).and(ARCHIVE_ITEMS.ID.eq(itemId)))
                .fetchOptional(this::toItemView);
    }

    public ProjectArchiveView markRunning(UUID archiveId) {
        var record = dsl.update(ARCHIVES)
                .set(ARCHIVES.STATUS, TaskStatus.RUNNING.name())
                .set(ARCHIVES.UPDATED_AT, OffsetDateTime.now())
                .where(ARCHIVES.ID.eq(archiveId))
                .returning()
                .fetchOne();
        return record == null ? null : toView(record);
    }

    public ProjectArchiveView markSucceeded(UUID archiveId, UUID storedArtifactId, long sizeBytes, String sha256, Map<String, ?> summary) {
        var record = dsl.update(ARCHIVES)
                .set(ARCHIVES.STATUS, TaskStatus.SUCCEEDED.name())
                .set(ARCHIVES.STORED_ARTIFACT_ID, storedArtifactId)
                .set(ARCHIVES.SIZE_BYTES, sizeBytes)
                .set(ARCHIVES.SHA256, sha256)
                .set(ARCHIVES.SUMMARY, toJsonb(summary))
                .set(ARCHIVES.UPDATED_AT, OffsetDateTime.now())
                .where(ARCHIVES.ID.eq(archiveId))
                .returning()
                .fetchOne();
        return record == null ? null : toView(record);
    }

    public ProjectArchiveView markFailed(UUID archiveId, Map<String, ?> summary) {
        var record = dsl.update(ARCHIVES)
                .set(ARCHIVES.STATUS, TaskStatus.FAILED.name())
                .set(ARCHIVES.SUMMARY, toJsonb(summary))
                .set(ARCHIVES.UPDATED_AT, OffsetDateTime.now())
                .where(ARCHIVES.ID.eq(archiveId))
                .returning()
                .fetchOne();
        return record == null ? null : toView(record);
    }

    private Condition filter(UUID projectId, ProjectArchiveListRequest request) {
        Condition condition = ARCHIVES.PROJECT_ID.eq(projectId);
        if (request.sourceRevisionId() != null) {
            condition = condition.and(ARCHIVES.SOURCE_REVISION_ID.eq(request.sourceRevisionId()));
        }
        if (request.status() != null) {
            condition = condition.and(ARCHIVES.STATUS.eq(request.status().name()));
        }
        if (request.createdFrom() != null) {
            condition = condition.and(ARCHIVES.CREATED_AT.ge(request.createdFrom()));
        }
        if (request.createdTo() != null) {
            condition = condition.and(ARCHIVES.CREATED_AT.le(request.createdTo()));
        }
        return condition;
    }

    private List<SortField<?>> sort(ProjectArchiveListRequest request) {
        Field<?> field = switch (blankToDefault(request.sortBy(), "")) {
            case "createdAt" -> ARCHIVES.CREATED_AT;
            case "status" -> ARCHIVES.STATUS;
            case "name" -> ARCHIVES.NAME;
            case "" -> null;
            default -> throw new IllegalArgumentException("Unsupported archive sort field: " + request.sortBy());
        };
        if (field == null) {
            return List.of(ARCHIVES.CREATED_AT.desc(), ARCHIVES.ID.desc());
        }
        return List.of("asc".equalsIgnoreCase(request.sortDirection()) ? field.asc().nullsLast() : field.desc().nullsLast(), ARCHIVES.ID.desc());
    }

    private ProjectArchiveView toView(cn.rvport.backend.jooq.tables.records.ArchivesRecord record) {
        return ProjectArchiveView.from(record, jsonbToMap(record.getSummary()));
    }

    private ProjectArchiveItemView toItemView(cn.rvport.backend.jooq.tables.records.ArchiveItemsRecord record) {
        return ProjectArchiveItemView.from(record, jsonbToArtifactRefs(record.getArtifactRefs()), jsonbToMap(record.getMetadata()));
    }

    private JSONB toJsonb(Object value) {
        try {
            return JSONB.valueOf(objectMapper.writeValueAsString(value == null ? Map.of() : value));
        } catch (JsonProcessingException ex) {
            throw new IllegalArgumentException("Archive JSON value is not serializable", ex);
        }
    }

    private Map<String, Object> jsonbToMap(JSONB jsonb) {
        if (jsonb == null || jsonb.data() == null || jsonb.data().isBlank()) {
            return Map.of();
        }
        try {
            return objectMapper.readValue(jsonb.data(), MAP_TYPE);
        } catch (Exception ex) {
            return Map.of();
        }
    }

    private List<ArchiveArtifactRef> jsonbToArtifactRefs(JSONB jsonb) {
        if (jsonb == null || jsonb.data() == null || jsonb.data().isBlank()) {
            return List.of();
        }
        try {
            return objectMapper.readValue(jsonb.data(), ARTIFACT_REFS_TYPE);
        } catch (Exception ex) {
            return List.of();
        }
    }

    private String blankToDefault(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value.trim();
    }
}
