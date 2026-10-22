package cn.rvport.backend.config;

import java.util.Locale;

public enum RvPortAppMode {
    API,
    WORKER,
    COMBINED;

    public static RvPortAppMode from(String value) {
        if (value == null || value.isBlank()) {
            return COMBINED;
        }
        return RvPortAppMode.valueOf(value.trim().replace('-', '_').toUpperCase(Locale.ROOT));
    }
}
