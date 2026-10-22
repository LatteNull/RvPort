package cn.rvport.backend.systemconfig;

public record SystemConfigEntry(
        String namespace,
        String key,
        String value,
        SystemConfigValueType valueType,
        boolean encrypted
) {
}
