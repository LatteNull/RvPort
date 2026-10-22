package cn.rvport.backend.archive;

import static cn.rvport.backend.jooq.tables.ArchiveCandidates.ARCHIVE_CANDIDATES;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.jooq.DSLContext;
import org.jooq.JSONB;
import org.springframework.stereotype.Repository;

@Repository
public class ArchiveCandidateRepository {

    private static final TypeReference<Map<String, Object>> MAP_TYPE = new TypeReference<>() {
    };
    private static final TypeReference<List<ArchiveArtifactRef>> ARTIFACT_REFS_TYPE = new TypeReference<>() {
    };

    private final DSLContext dsl;
    private final ObjectMapper objectMapper;

    public ArchiveCandidateRepository(DSLContext dsl, ObjectMapper objectMapper) {
        this.dsl = dsl;
        this.objectMapper = objectMapper;
    }

    public ArchiveCandidateView upsert(ArchiveCandidateUpsertCommand command) {
        var record = dsl.insertInto(ARCHIVE_CANDIDATES)
                .set(ARCHIVE_CANDIDATES.PROJECT_ID, command.projectId())
                .set(ARCHIVE_CANDIDATES.SOURCE_REVISION_ID, command.sourceRevisionId())
                .set(ARCHIVE_CANDIDATES.NODE_TYPE, command.nodeType().name())
                .set(ARCHIVE_CANDIDATES.CANDIDATE_TYPE, command.candidateType().name())
                .set(ARCHIVE_CANDIDATES.CANDIDATE_KEY, command.candidateKey())
                .set(ARCHIVE_CANDIDATES.RESOURCE_TYPE, command.resourceType())
                .set(ARCHIVE_CANDIDATES.RESOURCE_ID, command.resourceId())
                .set(ARCHIVE_CANDIDATES.TITLE, command.title())
                .set(ARCHIVE_CANDIDATES.SUMMARY, toJsonb(command.summary()))
                .set(ARCHIVE_CANDIDATES.ARTIFACT_REFS, toJsonb(command.artifactRefs()))
                .set(ARCHIVE_CANDIDATES.STATUS, ArchiveCandidateStatus.ACTIVE.name())
                .set(ARCHIVE_CANDIDATES.UPDATED_AT, OffsetDateTime.now())
                .onConflict(
                        ARCHIVE_CANDIDATES.PROJECT_ID,
                        ARCHIVE_CANDIDATES.SOURCE_REVISION_ID,
                        ARCHIVE_CANDIDATES.NODE_TYPE,
                        ARCHIVE_CANDIDATES.CANDIDATE_TYPE,
                        ARCHIVE_CANDIDATES.CANDIDATE_KEY
                )
                .doUpdate()
                .set(ARCHIVE_CANDIDATES.RESOURCE_TYPE, command.resourceType())
                .set(ARCHIVE_CANDIDATES.RESOURCE_ID, command.resourceId())
                .set(ARCHIVE_CANDIDATES.TITLE, command.title())
                .set(ARCHIVE_CANDIDATES.SUMMARY, toJsonb(command.summary()))
                .set(ARCHIVE_CANDIDATES.ARTIFACT_REFS, toJsonb(command.artifactRefs()))
                .set(ARCHIVE_CANDIDATES.STATUS, ArchiveCandidateStatus.ACTIVE.name())
                .set(ARCHIVE_CANDIDATES.UPDATED_AT, OffsetDateTime.now())
                .returning()
                .fetchOne();
        return toView(record);
    }

    public List<ArchiveCandidateView> listActive(UUID projectId, UUID sourceRevisionId) {
        return dsl.selectFrom(ARCHIVE_CANDIDATES)
                .where(ARCHIVE_CANDIDATES.PROJECT_ID.eq(projectId)
                        .and(ARCHIVE_CANDIDATES.SOURCE_REVISION_ID.eq(sourceRevisionId))
                        .and(ARCHIVE_CANDIDATES.STATUS.eq(ArchiveCandidateStatus.ACTIVE.name())))
                .orderBy(ARCHIVE_CANDIDATES.NODE_TYPE.asc(), ARCHIVE_CANDIDATES.CANDIDATE_TYPE.asc(), ARCHIVE_CANDIDATES.UPDATED_AT.desc())
                .fetch(this::toView);
    }

    private ArchiveCandidateView toView(cn.rvport.backend.jooq.tables.records.ArchiveCandidatesRecord record) {
        return ArchiveCandidateView.from(record, jsonbToMap(record.getSummary()), jsonbToArtifactRefs(record.getArtifactRefs()));
    }

    private JSONB toJsonb(Object value) {
        try {
            return JSONB.valueOf(objectMapper.writeValueAsString(value == null ? Map.of() : value));
        } catch (JsonProcessingException ex) {
            throw new IllegalArgumentException("Archive candidate JSON value is not serializable", ex);
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
}
