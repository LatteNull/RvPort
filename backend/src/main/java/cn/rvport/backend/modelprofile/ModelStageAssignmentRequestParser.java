package cn.rvport.backend.modelprofile;

import cn.rvport.backend.common.error.ApiException;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import tools.jackson.databind.JsonNode;

@Component
public class ModelStageAssignmentRequestParser {

    public ModelStageAssignmentRequest parse(JsonNode body) {
        if (body == null || !body.isObject()) {
            throw validation("请求体必须是 JSON object");
        }
        JsonNode assignments = body.get("assignments");
        if (assignments == null || !assignments.isArray()) {
            throw validation("assignments 必须是 array");
        }
        List<ModelStageAssignmentRequest.Entry> entries = new ArrayList<>();
        for (JsonNode node : assignments) {
            if (!node.isObject()) {
                throw validation("assignment 必须是 object");
            }
            node.propertyNames().forEach(field -> {
                if (!"stage".equals(field) && !"modelProfileId".equals(field) && !"agentRuntimeId".equals(field)) {
                    throw validation("请求包含不可写字段: " + field);
                }
            });
            entries.add(new ModelStageAssignmentRequest.Entry(
                    requiredString(node, "stage"),
                    requiredUuid(node, "modelProfileId"),
                    requiredUuid(node, "agentRuntimeId")
            ));
        }
        return new ModelStageAssignmentRequest(List.copyOf(entries));
    }

    private String requiredString(JsonNode body, String field) {
        JsonNode node = body.get(field);
        if (node == null || !node.isTextual() || node.textValue().isBlank()) {
            throw validation(field + " 必须是非空 string");
        }
        return node.textValue();
    }

    private UUID requiredUuid(JsonNode body, String field) {
        try {
            return UUID.fromString(requiredString(body, field));
        } catch (IllegalArgumentException ex) {
            throw validation(field + " 必须是 UUID");
        }
    }

    private ApiException validation(String message) {
        return new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", message);
    }
}
