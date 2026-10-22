package cn.rvport.backend.task;

import static cn.rvport.backend.jooq.tables.ToolRuns.TOOL_RUNS;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;
import org.jooq.DSLContext;
import org.jooq.JSONB;
import org.springframework.stereotype.Repository;

@Repository
public class ToolRunRepository {

    private final DSLContext dsl;
    private final ObjectMapper objectMapper;

    public ToolRunRepository(DSLContext dsl, ObjectMapper objectMapper) {
        this.dsl = dsl;
        this.objectMapper = objectMapper;
    }

    public UUID create(
            UUID projectId,
            UUID taskId,
            String toolName,
            String toolVersion,
            String commandSummary,
            TaskStatus status,
            OffsetDateTime startedAt
    ) {
        return dsl.insertInto(TOOL_RUNS)
                .set(TOOL_RUNS.PROJECT_ID, projectId)
                .set(TOOL_RUNS.TASK_ID, taskId)
                .set(TOOL_RUNS.TOOL_NAME, toolName)
                .set(TOOL_RUNS.TOOL_VERSION, toolVersion)
                .set(TOOL_RUNS.COMMAND_SUMMARY, commandSummary)
                .set(TOOL_RUNS.STATUS, status.name())
                .set(TOOL_RUNS.STARTED_AT, startedAt)
                .returning(TOOL_RUNS.ID)
                .fetchOne(TOOL_RUNS.ID);
    }

    public void finish(UUID toolRunId, TaskStatus status, Integer exitCode, Map<String, ?> summary) {
        dsl.update(TOOL_RUNS)
                .set(TOOL_RUNS.STATUS, status.name())
                .set(TOOL_RUNS.EXIT_CODE, exitCode)
                .set(TOOL_RUNS.SUMMARY, toJsonb(summary))
                .set(TOOL_RUNS.FINISHED_AT, OffsetDateTime.now())
                .where(TOOL_RUNS.ID.eq(toolRunId))
                .execute();
    }

    private JSONB toJsonb(Map<String, ?> summary) {
        try {
            return JSONB.valueOf(objectMapper.writeValueAsString(summary == null ? Map.of() : summary));
        } catch (JsonProcessingException ex) {
            return JSONB.valueOf("{}");
        }
    }
}
