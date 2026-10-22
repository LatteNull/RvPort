package cn.rvport.backend.codexprovider;

public record CodexProviderResolvedConfig(
        boolean enabled,
        String executablePath,
        CodexProviderType modelProviderType,
        String baseUrl,
        String model,
        CodexProviderWireApi wireApi,
        String apiKey,
        int timeoutSeconds,
        int maxRuntimeSeconds
) {
}
