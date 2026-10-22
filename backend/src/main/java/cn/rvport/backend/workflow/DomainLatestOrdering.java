package cn.rvport.backend.workflow;

import cn.rvport.backend.task.TaskStatus;
import org.jooq.Field;
import org.jooq.SortField;
import org.jooq.impl.DSL;

public final class DomainLatestOrdering {

    private DomainLatestOrdering() {
    }

    public static SortField<Integer> activeFirst(Field<String> status) {
        return DSL.when(status.in(
                        TaskStatus.PENDING.name(),
                        TaskStatus.QUEUED.name(),
                        TaskStatus.RUNNING.name()), 0)
                .otherwise(1)
                .asc();
    }
}
