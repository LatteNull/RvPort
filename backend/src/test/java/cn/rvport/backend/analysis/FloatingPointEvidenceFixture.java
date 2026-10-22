package cn.rvport.backend.analysis;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.util.List;

enum FloatingPointEvidenceFixture {
    BILINGUAL,
    LEGACY_WITHOUT_DESCRIPTIONS,
    LEGACY_WITH_PARTIAL_DESCRIPTIONS,
    LEGACY_WITHOUT_CHAIN,
    EMPTY_STEPS;

    ObjectNode detail(ObjectMapper mapper) throws JsonProcessingException {
        ObjectNode detail = (ObjectNode) mapper.readTree("""
                {"id":"fp-1","semanticDigest":"digest",
                 "fact":{"primaryLocation":{"file":"main.cpp","line":1,"column":8}},
                 "conclusion":{"findingCode":"FP_EQUALITY","category":"precision","severity":"high",
                   "status":"confirmed","title":"浮点比较","titleEn":"Floating comparison"},
                 "evidenceChain":{"status":"partial","reasonCodes":["IR_UNAVAILABLE"],"steps":[
                   {"id":"step-source","kind":"sourceObservation","status":"complete",
                    "title":"源码浮点比较","titleEn":"Source floating-point comparison",
                    "reason":"源码包含比较表达式：x == 0.1，位置为 main.cpp:1。",
                    "reasonEn":"Source contains comparison x == 0.1 at main.cpp:1.",
                    "references":[{"type":"sourceFact","id":"source-1"}],"reasonCodes":[]},
                   {"id":"step-assessment","kind":"assessment","status":"partial",
                    "title":"精度风险尚需确认","titleEn":"Precision risk needs confirmation",
                    "reason":"仅有源码证据，缺少 IR；不能确认优化后的行为。",
                    "reasonEn":"Only source evidence is available; missing IR prevents confirming optimized behavior.",
                    "references":[{"type":"assessment","id":"assessment-1"}],
                    "reasonCodes":["IR_UNAVAILABLE"]}]}}
                """);
        ArrayNode steps = (ArrayNode) detail.path("evidenceChain").path("steps");
        switch (this) {
            case BILINGUAL -> { }
            case LEGACY_WITHOUT_DESCRIPTIONS -> steps.forEach(step -> ((ObjectNode) step)
                    .remove(List.of("title", "titleEn", "reason", "reasonEn")));
            case LEGACY_WITH_PARTIAL_DESCRIPTIONS -> {
                ((ObjectNode) steps.get(0)).remove(List.of("titleEn", "reasonEn"));
                ((ObjectNode) steps.get(1)).remove("reason");
            }
            case LEGACY_WITHOUT_CHAIN -> detail.remove("evidenceChain");
            case EMPTY_STEPS -> steps.removeAll();
        }
        return detail;
    }
}
