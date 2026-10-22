package cn.rvport.backend.modelprofile;

import java.util.Set;
import java.util.UUID;

public record ModelProfileRequest(
        String name,
        Boolean enabled,
        String executablePath,
        String modelProviderType,
        String baseUrl,
        String model,
        String wireApi,
        String apiKey,
        boolean apiKeyPresent,
        UUID agentRuntimeId,
        Integer timeoutSeconds,
        Integer maxRuntimeSeconds,
        Set<String> presentFields
) {
    public ModelProfileRequest(
            String name,
            Boolean enabled,
            String executablePath,
            String modelProviderType,
            String baseUrl,
            String model,
            String wireApi,
            String apiKey,
            boolean apiKeyPresent,
            Integer timeoutSeconds,
            Integer maxRuntimeSeconds,
            Set<String> presentFields
    ) {
        this(name, enabled, executablePath, modelProviderType, baseUrl, model, wireApi, apiKey, apiKeyPresent,
                null, timeoutSeconds, maxRuntimeSeconds, presentFields);
    }

    public boolean hasField(String field) {
        return presentFields != null && presentFields.contains(field);
    }
}
