package cn.rvport.backend.archive;

import cn.rvport.backend.task.TaskResponse;
import java.util.UUID;

public record ProjectArchiveCreateResponse(
        UUID archiveId,
        UUID sourceRevisionId,
        TaskResponse task
) {
}
