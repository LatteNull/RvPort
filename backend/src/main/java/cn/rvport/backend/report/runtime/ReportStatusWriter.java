package cn.rvport.backend.report.runtime;

import cn.rvport.backend.report.ReportRepository;
import cn.rvport.backend.report.ReportView;
import cn.rvport.backend.task.TaskStatus;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ReportStatusWriter {

    private final ReportRepository reportRepository;

    public ReportStatusWriter(ReportRepository reportRepository) {
        this.reportRepository = reportRepository;
    }

    @Transactional
    public ReportView updateStatus(UUID reportId, TaskStatus status, Map<String, ?> summary) {
        return reportRepository.updateStatus(reportId, status, summary);
    }

    @Transactional
    public ReportView markSucceeded(UUID reportId, Map<String, ?> summary, String riskLevel) {
        return reportRepository.markSucceeded(reportId, summary, riskLevel);
    }
}
