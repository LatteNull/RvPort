package cn.rvport.backend.kb;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import java.util.List;
import java.util.Map;

@JsonIgnoreProperties(ignoreUnknown = true)
public record KbScannerResult(
        String schemaVersion,
        Scan scan,
        Map<String, Object> project,
        Map<String, Object> summary,
        List<Finding> findings,
        List<Map<String, Object>> diagnostics
) {
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Scan(
            String id,
            Map<String, Object> tool,
            Map<String, Object> scope,
            List<String> artifactNames,
            List<Map<String, Object>> knowledgeSources
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Finding(
            String id,
            Fact fact,
            Conclusion conclusion,
            List<Occurrence> occurrences,
            String primaryOccurrenceId,
            Map<String, Object> evidenceChain
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Fact(
            String kind,
            String symbol,
            String matchedText,
            Location primaryLocation,
            List<Map<String, Object>> provenance
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Conclusion(
            String title,
            String severity,
            Double confidence,
            String findingType,
            Boolean actionable,
            Boolean blocking,
            String archReachability,
            String status,
            String reason,
            String suggestion
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Occurrence(
            String id,
            String kind,
            Location location,
            String configuration,
            String selectionStatus,
            String status,
            List<String> reasonCodes,
            List<Map<String, Object>> provenance
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Location(
            String file,
            Span span,
            Map<String, Object> context
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Span(
            Position start,
            Position end
    ) {
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Position(
            Integer line,
            Integer column
    ) {
    }
}
