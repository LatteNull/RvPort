package cn.rvport.backend.modelprofile;

import cn.rvport.backend.common.error.ApiException;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import tools.jackson.databind.JsonNode;

@Component
public class ModelProfileAgentProbeRequestParser {

    private static final Set<String> ALLOWED_FIELDS = Set.of("agentRuntimeIds");

    public ModelProfileAgentProbeRequest parse(JsonNode body) {
        if (body == null || !body.isObject()) {
            throw validation("请求体必须是 JSON object");
        }
        body.propertyNames().forEach(field -> {
            if (!ALLOWED_FIELDS.contains(field)) {
                throw validation("请求包含不可写字段: " + field);
            }
        });
        JsonNode node = body.get("agentRuntimeIds");
        if (node == null || !node.isArray()) {
            throw validation("agentRuntimeIds 必须是 UUID array");
        }
        List<UUID> ids = new ArrayList<>();
        Set<UUID> seen = new HashSet<>();
        for (JsonNode item : node) {
            if (!item.isTextual()) {
                throw validation("agentRuntimeIds 必须是 UUID array");
            }
            UUID id;
            try {
                id = UUID.fromString(item.textValue());
            } catch (IllegalArgumentException ex) {
                throw validation("agentRuntimeIds 必须是 UUID array");
            }
            if (!seen.add(id)) {
                throw validation("agentRuntimeIds 不能重复");
            }
            ids.add(id);
        }
        if (ids.isEmpty()) {
            throw validation("agentRuntimeIds 不能为空");
        }
        if (ids.size() > 10) {
            throw validation("agentRuntimeIds 不能超过 10 个");
        }
        return new ModelProfileAgentProbeRequest(List.copyOf(ids));
    }

    private ApiException validation(String message) {
        return new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", message);
    }
}
