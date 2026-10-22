package cn.rvport.backend.migration;

import cn.rvport.backend.report.ReportRepository;
import cn.rvport.backend.report.ReportView;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class NodeReportInclusionService {

    private final MigrationInputRepository migrationInputRepository;
    private final ReportRepository reportRepository;

    public NodeReportInclusionService(MigrationInputRepository migrationInputRepository, ReportRepository reportRepository) {
        this.migrationInputRepository = migrationInputRepository;
        this.reportRepository = reportRepository;
    }

    @Transactional(readOnly = true)
    public NodeReportInclusionState state(
            UUID projectId,
            UUID sourceRevisionId,
            MigrationInputSourceType sourceType,
            UUID sourceRefId
    ) {
        return states(projectId, sourceRevisionId, sourceType, List.of(sourceRefId))
                .getOrDefault(sourceRefId, NodeReportInclusionState.empty());
    }

    @Transactional(readOnly = true)
    public Map<UUID, NodeReportInclusionState> states(
            UUID projectId,
            UUID sourceRevisionId,
            MigrationInputSourceType sourceType,
            List<UUID> sourceRefIds
    ) {
        if (sourceRefIds == null || sourceRefIds.isEmpty()) {
            return Map.of();
        }
        Map<UUID, MigrationInputRefView> refs = migrationInputRepository.findBySourceRefs(projectId, sourceRevisionId, sourceType, sourceRefIds);
        if (refs == null) {
            refs = Map.of();
        }
        ReportView latestReport = reportRepository.latestSucceeded(projectId, sourceRevisionId).orElse(null);
        List<UUID> rawIncludedRefIds = latestReport == null ? List.of() : reportRepository.listMigrationInputIds(latestReport.id());
        Set<UUID> includedRefIds = rawIncludedRefIds == null ? Set.of() : new HashSet<>(rawIncludedRefIds);

        Map<UUID, NodeReportInclusionState> result = new LinkedHashMap<>();
        for (UUID sourceRefId : sourceRefIds) {
            MigrationInputRefView ref = refs.get(sourceRefId);
            if (ref == null) {
                result.put(sourceRefId, NodeReportInclusionState.empty());
                continue;
            }
            boolean confirmed = ref.status() == MigrationInputStatus.CONFIRMED;
            boolean included = includedRefIds.contains(ref.id());
            result.put(sourceRefId, new NodeReportInclusionState(
                    ref.id(),
                    ref.status(),
                    confirmed,
                    included,
                    included ? latestReport.id() : null
            ));
        }
        return result;
    }
}
