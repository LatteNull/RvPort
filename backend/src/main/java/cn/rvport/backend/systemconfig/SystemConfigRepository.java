package cn.rvport.backend.systemconfig;

import static cn.rvport.backend.jooq.tables.SystemConfigs.SYSTEM_CONFIGS;

import cn.rvport.backend.jooq.tables.records.SystemConfigsRecord;
import java.time.OffsetDateTime;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.jooq.DSLContext;
import org.springframework.stereotype.Repository;

@Repository
public class SystemConfigRepository {

    private final DSLContext dsl;

    public SystemConfigRepository(DSLContext dsl) {
        this.dsl = dsl;
    }

    public Map<String, SystemConfigEntry> findNamespace(String namespace) {
        Map<String, SystemConfigEntry> entries = new LinkedHashMap<>();
        dsl.selectFrom(SYSTEM_CONFIGS)
                .where(SYSTEM_CONFIGS.NAMESPACE.eq(namespace))
                .orderBy(SYSTEM_CONFIGS.CONFIG_KEY.asc())
                .forEach(record -> entries.put(record.getConfigKey(), map(record)));
        return entries;
    }

    public Optional<SystemConfigEntry> find(String namespace, String key) {
        return dsl.selectFrom(SYSTEM_CONFIGS)
                .where(SYSTEM_CONFIGS.NAMESPACE.eq(namespace)
                        .and(SYSTEM_CONFIGS.CONFIG_KEY.eq(key)))
                .fetchOptional()
                .map(this::map);
    }

    public void upsert(String namespace, String key, String value, SystemConfigValueType valueType, boolean encrypted, UUID updatedBy) {
        dsl.insertInto(SYSTEM_CONFIGS)
                .set(SYSTEM_CONFIGS.NAMESPACE, namespace)
                .set(SYSTEM_CONFIGS.CONFIG_KEY, key)
                .set(SYSTEM_CONFIGS.CONFIG_VALUE, value)
                .set(SYSTEM_CONFIGS.VALUE_TYPE, valueType.name())
                .set(SYSTEM_CONFIGS.ENCRYPTED, encrypted)
                .set(SYSTEM_CONFIGS.UPDATED_BY, updatedBy)
                .set(SYSTEM_CONFIGS.UPDATED_AT, OffsetDateTime.now())
                .onConflict(SYSTEM_CONFIGS.NAMESPACE, SYSTEM_CONFIGS.CONFIG_KEY)
                .doUpdate()
                .set(SYSTEM_CONFIGS.CONFIG_VALUE, value)
                .set(SYSTEM_CONFIGS.VALUE_TYPE, valueType.name())
                .set(SYSTEM_CONFIGS.ENCRYPTED, encrypted)
                .set(SYSTEM_CONFIGS.UPDATED_BY, updatedBy)
                .set(SYSTEM_CONFIGS.UPDATED_AT, OffsetDateTime.now())
                .execute();
    }

    public void delete(String namespace, String key) {
        dsl.deleteFrom(SYSTEM_CONFIGS)
                .where(SYSTEM_CONFIGS.NAMESPACE.eq(namespace)
                        .and(SYSTEM_CONFIGS.CONFIG_KEY.eq(key)))
                .execute();
    }

    private SystemConfigEntry map(SystemConfigsRecord record) {
        return new SystemConfigEntry(
                record.getNamespace(),
                record.getConfigKey(),
                record.getConfigValue(),
                SystemConfigValueType.valueOf(record.getValueType()),
                Boolean.TRUE.equals(record.getEncrypted())
        );
    }
}
