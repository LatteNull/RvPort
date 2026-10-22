package cn.rvport.backend.analysis;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import java.util.Locale;
import java.util.Set;

public record SpecializedFindingListRequest(
        @Min(1) Integer page,
        @Min(1) @Max(200) Integer pageSize,
        String severity,
        String status,
        String category,
        String code,
        String filePath,
        String keyword,
        String sortBy,
        String sortDirection
) {
    private static final Set<String> SORTS = Set.of("createdAt", "severity", "filePath", "startLine", "code");

    public int normalizedPage() { return page == null || page < 1 ? 1 : page; }
    public int normalizedPageSize() { return pageSize == null ? 20 : Math.max(1, Math.min(200, pageSize)); }
    public String normalizedSortBy() { return sortBy != null && SORTS.contains(sortBy) ? sortBy : "createdAt"; }
    public boolean ascending() { return "asc".equalsIgnoreCase(sortDirection); }
    public String normalizedSeverity() { return upper(severity); }
    public String normalizedStatus() { return upper(status); }
    private static String upper(String value) {
        return value == null || value.isBlank() ? null : value.trim().toUpperCase(Locale.ROOT);
    }
}
