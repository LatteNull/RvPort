package cn.rvport.backend.buildvalidation.bitcode;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;

/** Java/Python 共用的 UTF-8 canonical JSON 身份算法。 */
public final class BitcodeCanonicalIdentity {

    private static final ObjectMapper MAPPER = new ObjectMapper().findAndRegisterModules();

    private BitcodeCanonicalIdentity() {
    }

    public static String digest(Object value, String... excludedFields) {
        JsonNode canonical = canonicalize(MAPPER.valueToTree(value), Set.of(excludedFields));
        try {
            byte[] bytes = MAPPER.writeValueAsString(canonical).getBytes(StandardCharsets.UTF_8);
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
        } catch (NoSuchAlgorithmException | java.io.IOException ex) {
            throw new IllegalStateException("无法计算 BC canonical identity", ex);
        }
    }

    static JsonNode canonicalize(JsonNode value, Set<String> excludedFields) {
        if (value.isObject()) {
            ObjectNode result = MAPPER.createObjectNode();
            TreeMap<String, JsonNode> fields = new TreeMap<>();
            Iterator<Map.Entry<String, JsonNode>> iterator = value.fields();
            iterator.forEachRemaining(entry -> {
                if (!excludedFields.contains(entry.getKey())) {
                    fields.put(entry.getKey(), canonicalize(entry.getValue(), excludedFields));
                }
            });
            fields.forEach(result::set);
            return result;
        }
        if (value.isArray()) {
            ArrayNode result = MAPPER.createArrayNode();
            List<JsonNode> elements = new ArrayList<>();
            value.forEach(item -> elements.add(canonicalize(item, excludedFields)));
            elements.sort(Comparator.comparing(JsonNode::toString));
            elements.forEach(result::add);
            return result;
        }
        return value.deepCopy();
    }
}
