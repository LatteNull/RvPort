package cn.rvport.backend.kb;

import cn.rvport.backend.buildvalidation.BuildValidationRunView;
import cn.rvport.backend.buildvalidation.BuildValidationScope;
import cn.rvport.backend.task.TaskStatus;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

public final class KbContextFixtures {
    public static final UUID ENV = UUID.fromString("00000000-0000-0000-0000-000000000011");
    public static final UUID BUILD = UUID.fromString("00000000-0000-0000-0000-000000000012");
    public static final KbExecutionContext CONTEXT = new KbExecutionContext(ENV, 7L, BUILD);
    private KbContextFixtures() {}

    public static BuildValidationRunView build(UUID project, UUID source) {
        return build(project, source, ENV, 7L, BUILD, TaskStatus.SUCCEEDED, BuildValidationScope.SOURCE_ONLY);
    }

    public static BuildValidationRunView build(UUID project, UUID source, UUID environment, Long version,
            UUID id, TaskStatus status, BuildValidationScope scope) {
        return new BuildValidationRunView(id, project, UUID.randomUUID(), source, environment, scope,
                null, version, null, "hash", "make", "/source", 60, 0, status, null,
                null, null, null, null, null, OffsetDateTime.now(), Map.of(), Map.of());
    }

    public static KbScanContextService.Selection ready(UUID project, UUID source) {
        return new KbScanContextService.Selection(project, source, ENV, 7L, build(project, source));
    }

    public static KbScanView scan(UUID project, UUID source, TaskStatus status, KbExecutionContext context) {
        return new KbScanView(UUID.randomUUID(), project, UUID.randomUUID(), source, "rules", Map.of(),
                status, Map.of(), null, null, context);
    }
}
