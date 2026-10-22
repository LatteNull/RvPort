package cn.rvport.backend.source;

public record LatestSourceCompareResponse(
        LatestSourceCompareStatus status,
        LatestSourceCompareEmptyReason emptyReason,
        SourceRevisionResponse currentRevision,
        SourceRevisionResponse previousRevision,
        RecheckRunResponse recheckRun,
        DiffSummaryResponse diffSummary,
        DiffItemsPageLinkResponse diffItems
) {
}
