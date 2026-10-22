package cn.rvport.backend.source;

public record DiffItemsPageLinkResponse(
        String href,
        int defaultPage,
        int defaultPageSize,
        long total
) {
}
