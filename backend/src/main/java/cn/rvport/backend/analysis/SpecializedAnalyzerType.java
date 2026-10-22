package cn.rvport.backend.analysis;

public enum SpecializedAnalyzerType {
    FLOATING_POINT,
    MEMORY_ORDER;

    public String displayName() {
        return this == FLOATING_POINT ? "浮点精度分析" : "强弱内存序分析";
    }
}
