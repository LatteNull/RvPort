package cn.rvport.backend.analysis;

import java.util.List;
import java.util.Map;

/** 浮点专项分析使用的编译条目分母，禁止混用 raw command 与项目 TU。 */
public record CompileEntryClassification(
        int rawCommandCount,
        int cCppCandidateCount,
        int projectTranslationUnitCount,
        List<ProjectUnit> projectUnits,
        Map<String, Integer> excludedReasons
) {
    public record ProjectUnit(String path, String contextKey) {
    }

    public Map<String, Object> safeSummary() {
        return Map.of(
                "rawCommandCount", rawCommandCount,
                "cCppCandidateCount", cCppCandidateCount,
                "projectTranslationUnitCount", projectTranslationUnitCount,
                "excludedCount", excludedReasons.values().stream().mapToInt(Integer::intValue).sum(),
                "excludedReasons", excludedReasons);
    }
}
