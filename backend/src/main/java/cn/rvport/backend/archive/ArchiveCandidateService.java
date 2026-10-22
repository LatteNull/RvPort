package cn.rvport.backend.archive;

import cn.rvport.backend.common.error.ApiException;
import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ArchiveCandidateService {

    private final ArchiveCandidateRepository repository;

    public ArchiveCandidateService(ArchiveCandidateRepository repository) {
        this.repository = repository;
    }

    @Transactional
    public ArchiveCandidateView upsert(ArchiveCandidateUpsertCommand command) {
        validate(command);
        return repository.upsert(command);
    }

    @Transactional(readOnly = true)
    public List<ArchiveCandidateView> listActive(UUID projectId, UUID sourceRevisionId) {
        return repository.listActive(projectId, sourceRevisionId);
    }

    private void validate(ArchiveCandidateUpsertCommand command) {
        if (command.projectId() == null || command.sourceRevisionId() == null || command.nodeType() == null
                || command.candidateType() == null || blank(command.candidateKey()) || blank(command.resourceType())
                || blank(command.title())) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "ARCHIVE_CANDIDATE_INVALID", "归档候选输入不完整");
        }
        validateSafe(command.summary());
        validateSafe(command.artifactRefs());
    }

    @SuppressWarnings("unchecked")
    private void validateSafe(Object value) {
        if (value == null) {
            return;
        }
        if (value instanceof Map<?, ?> map) {
            for (Map.Entry<?, ?> entry : map.entrySet()) {
                String key = String.valueOf(entry.getKey());
                if (sensitiveKey(key)) {
                    throw unsafe();
                }
                validateSafe(entry.getValue());
            }
            return;
        }
        if (value instanceof Collection<?> collection) {
            for (Object item : collection) {
                validateSafe(item);
            }
            return;
        }
        if (value instanceof ArchiveArtifactRef ref) {
            validateText(ref.format());
            validateText(ref.artifactType());
            validateText(ref.contentType());
            validateText(ref.filename());
            return;
        }
        if (value instanceof String text) {
            validateText(text);
        }
    }

    private void validateText(String value) {
        if (value == null || value.isBlank()) {
            return;
        }
        String normalized = value.replace('\\', '/');
        if (normalized.matches("^[A-Za-z]:/.*") || normalized.startsWith("/") || containsParentSegment(normalized)
                || normalized.matches("(?i).*\\b(password|private[_-]?key|passphrase|secret|token)\\b.*")) {
            throw unsafe();
        }
    }

    private boolean sensitiveKey(String key) {
        return key != null && key.matches("(?i).*(password|private[_-]?key|passphrase|secret|token|object[_-]?key|bucket).*");
    }

    private boolean containsParentSegment(String value) {
        for (String segment : value.split("/", -1)) {
            if ("..".equals(segment)) {
                return true;
            }
        }
        return false;
    }

    private boolean blank(String value) {
        return value == null || value.isBlank();
    }

    private ApiException unsafe() {
        return new ApiException(HttpStatus.BAD_REQUEST, "ARCHIVE_CANDIDATE_UNSAFE_CONTENT", "归档候选包含不允许保存的敏感内容");
    }
}
