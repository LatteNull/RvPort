package cn.rvport.backend.config;

import java.io.IOException;
import java.util.Map;
import org.springframework.boot.context.properties.bind.Bindable;
import org.springframework.boot.context.properties.bind.Binder;
import org.springframework.boot.env.YamlPropertySourceLoader;
import org.springframework.core.env.MapPropertySource;
import org.springframework.core.env.StandardEnvironment;
import org.springframework.core.io.ClassPathResource;

final class ApplicationYamlTestSupport {

    private ApplicationYamlTestSupport() {
    }

    static StandardEnvironment environment() {
        return environment(Map.of());
    }

    static StandardEnvironment environment(Map<String, Object> overrides) {
        StandardEnvironment environment = new StandardEnvironment();
        try {
            new YamlPropertySourceLoader().load("application", new ClassPathResource("application.yml"))
                    .forEach(environment.getPropertySources()::addLast);
        } catch (IOException exception) {
            throw new IllegalStateException("无法读取 application.yml", exception);
        }
        if (!overrides.isEmpty()) {
            environment.getPropertySources().addFirst(new MapPropertySource("test-overrides", overrides));
        }
        return environment;
    }

    static <T> T bind(StandardEnvironment environment, String prefix, Class<T> type) {
        return Binder.get(environment).bind(prefix, Bindable.of(type))
                .orElseThrow(() -> new IllegalStateException("无法绑定配置: " + prefix));
    }
}
