package cn.rvport.backend.testcomparison.runtime;

import cn.rvport.backend.testcomparison.TestComparisonOverallStatus;
import cn.rvport.backend.testcomparison.TestComparisonParsedFinding;
import cn.rvport.backend.testcomparison.TestComparisonRiskLevel;
import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

public record TestComparisonAgentResult(
        TestComparisonOverallStatus overallStatus,
        TestComparisonRiskLevel riskLevel,
        BigDecimal confidence,
        String summary,
        String recommendation,
        Map<String, Object> sourceStats,
        Map<String, Object> targetStats,
        List<TestComparisonParsedFinding> findings,
        String rawOutput,
        Map<String, Object> agentOutput
) {
}
