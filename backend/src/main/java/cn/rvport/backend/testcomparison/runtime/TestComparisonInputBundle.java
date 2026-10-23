package cn.rvport.backend.testcomparison.runtime;

import java.util.Map;

public record TestComparisonInputBundle(
        Map<String, Object> payload,
        boolean truncated,
        Map<String, Object> summary
) {
}
