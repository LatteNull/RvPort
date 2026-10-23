package cn.rvport.backend.testcomparison.runtime;

import java.util.Map;

public class TestComparisonAgentOutputException extends RuntimeException {

    private final String code;
    private final Map<String, Object> agentOutput;

    public TestComparisonAgentOutputException(String code, String message, Map<String, Object> agentOutput) {
        super(message);
        this.code = code;
        this.agentOutput = agentOutput == null ? Map.of() : agentOutput;
    }

    public String code() {
        return code;
    }

    public Map<String, Object> agentOutput() {
        return agentOutput;
    }
}
