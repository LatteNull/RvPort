package cn.rvport.backend.workflow;

public record DomainLatestResponse<T>(
        ProjectContextSnapshot context,
        DomainLatestFreshness freshness,
        DomainLatestExecutionResponse execution,
        T result
) {
    public static <T> DomainLatestResponse<T> empty(ProjectContextSnapshot context) {
        return new DomainLatestResponse<>(context, DomainLatestFreshness.EMPTY, null, null);
    }

    public static <T> DomainLatestResponse<T> current(
            ProjectContextSnapshot context,
            DomainLatestExecutionResponse execution,
            T result
    ) {
        return new DomainLatestResponse<>(context, DomainLatestFreshness.CURRENT, execution, result);
    }

    public static <T> DomainLatestResponse<T> stale(
            ProjectContextSnapshot context,
            DomainLatestExecutionResponse execution,
            T result
    ) {
        return new DomainLatestResponse<>(context, DomainLatestFreshness.STALE, execution, result);
    }
}
