package cn.rvport.backend.artifact;

import static cn.rvport.backend.jooq.tables.StoredArtifacts.STORED_ARTIFACTS;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.jooq.DSLContext;
import org.jooq.JSONB;
import org.springframework.stereotype.Repository;

@Repository
public class StoredArtifactRepository {

    private static final TypeReference<Map<String, Object>> MAP_TYPE = new TypeReference<>() {
    };

    private final DSLContext dsl;
    private final ObjectMapper objectMapper;

    public StoredArtifactRepository(DSLContext dsl, ObjectMapper objectMapper) {
        this.dsl = dsl;
        this.objectMapper = objectMapper;
    }

    public Optional<StoredArtifactView> findById(UUID artifactId) {
        return dsl.selectFrom(STORED_ARTIFACTS)
                .where(STORED_ARTIFACTS.ID.eq(artifactId))
                .fetchOptional(record -> StoredArtifactView.from(record, jsonbToMap(record.getSummary())));
    }

    public Optional<StoredArtifactView> findByOwner(StoredArtifactOwnerType ownerType, UUID ownerId, String artifactType) {
        return dsl.selectFrom(STORED_ARTIFACTS)
                .where(STORED_ARTIFACTS.OWNER_TYPE.eq(ownerType.name())
                        .and(STORED_ARTIFACTS.OWNER_ID.eq(ownerId))
                        .and(STORED_ARTIFACTS.ARTIFACT_TYPE.eq(artifactType)))
                .fetchOptional(record -> StoredArtifactView.from(record, jsonbToMap(record.getSummary())));
    }

    public List<StoredArtifactView> listByOwner(StoredArtifactOwnerType ownerType, UUID ownerId) {
        return dsl.selectFrom(STORED_ARTIFACTS)
                .where(STORED_ARTIFACTS.OWNER_TYPE.eq(ownerType.name())
                        .and(STORED_ARTIFACTS.OWNER_ID.eq(ownerId)))
                .orderBy(STORED_ARTIFACTS.CREATED_AT.desc(), STORED_ARTIFACTS.ARTIFACT_TYPE.asc())
                .fetch(record -> StoredArtifactView.from(record, jsonbToMap(record.getSummary())));
    }

    public StoredArtifactView upsert(
            UUID id,
            UUID projectId,
            UUID taskId,
            StoredArtifactOwnerType ownerType,
            UUID ownerId,
            String artifactType,
            String bucket,
            String objectKey,
            String contentType,
            long sizeBytes,
            String sha256,
            Map<String, ?> summary
    ) {
        var record = dsl.insertInto(STORED_ARTIFACTS)
                .set(STORED_ARTIFACTS.ID, id)
                .set(STORED_ARTIFACTS.PROJECT_ID, projectId)
                .set(STORED_ARTIFACTS.TASK_ID, taskId)
                .set(STORED_ARTIFACTS.OWNER_TYPE, ownerType.name())
                .set(STORED_ARTIFACTS.OWNER_ID, ownerId)
                .set(STORED_ARTIFACTS.ARTIFACT_TYPE, artifactType)
                .set(STORED_ARTIFACTS.BUCKET, bucket)
                .set(STORED_ARTIFACTS.OBJECT_KEY, objectKey)
                .set(STORED_ARTIFACTS.CONTENT_TYPE, contentType)
                .set(STORED_ARTIFACTS.SIZE_BYTES, sizeBytes)
                .set(STORED_ARTIFACTS.SHA256, sha256)
                .set(STORED_ARTIFACTS.SUMMARY, toJsonb(summary))
                .onConflict(STORED_ARTIFACTS.OWNER_TYPE, STORED_ARTIFACTS.OWNER_ID, STORED_ARTIFACTS.ARTIFACT_TYPE)
                .doUpdate()
                .set(STORED_ARTIFACTS.TASK_ID, taskId)
                .set(STORED_ARTIFACTS.BUCKET, bucket)
                .set(STORED_ARTIFACTS.OBJECT_KEY, objectKey)
                .set(STORED_ARTIFACTS.CONTENT_TYPE, contentType)
                .set(STORED_ARTIFACTS.SIZE_BYTES, sizeBytes)
                .set(STORED_ARTIFACTS.SHA256, sha256)
                .set(STORED_ARTIFACTS.SUMMARY, toJsonb(summary))
                .set(STORED_ARTIFACTS.CREATED_AT, OffsetDateTime.now())
                .returning()
                .fetchOne();
        return StoredArtifactView.from(record, jsonbToMap(record.getSummary()));
    }

    public void delete(UUID artifactId) {
        dsl.deleteFrom(STORED_ARTIFACTS)
                .where(STORED_ARTIFACTS.ID.eq(artifactId))
                .execute();
    }

    public void deleteByProject(UUID projectId) {
        dsl.deleteFrom(STORED_ARTIFACTS)
                .where(STORED_ARTIFACTS.PROJECT_ID.eq(projectId))
                .execute();
    }

    private JSONB toJsonb(Map<String, ?> value) {
        try {
            return JSONB.valueOf(objectMapper.writeValueAsString(value == null ? Map.of() : value));
        } catch (JsonProcessingException ex) {
            throw new IllegalArgumentException("Artifact summary is not JSON serializable", ex);
        }
    }

    private Map<String, Object> jsonbToMap(JSONB jsonb) {
        if (jsonb == null || jsonb.data() == null) {
            return Map.of();
        }
        try {
            return objectMapper.readValue(jsonb.data(), MAP_TYPE);
        } catch (Exception ex) {
            return Map.of();
        }
    }
}
